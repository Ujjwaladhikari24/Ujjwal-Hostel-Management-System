"""Authentication: student registration, student login, admin login, logout."""
from datetime import datetime

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from ..extensions import db
from ..models import Notification, Setting, Student, User
from ..utils import clean, log_action, password_problem, save_upload, valid_email, valid_phone

auth_bp = Blueprint("auth", __name__)


def _safe_next(target, fallback):
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return fallback


def _home_for(user):
    return "admin.overview" if user.role == "admin" else "student.dashboard"


# --------------------------------------------------------------------------- #
#  Student registration
# --------------------------------------------------------------------------- #
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(_home_for(current_user)))
    if not Setting.get_bool("registration_open", True):
        flash("Student self-registration is currently closed. Please contact the hostel office.", "warning")
        return redirect(url_for("auth.login"))

    form = {}
    if request.method == "POST":
        form = {k: clean(v) for k, v in request.form.items()}
        errors = []

        name = form.get("name", "")
        email = form.get("email", "").lower()
        phone = form.get("phone", "")
        enrollment = form.get("enrollment_no", "").upper()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        if len(name) < 3:
            errors.append("Please enter your full name (at least 3 characters).")
        if not valid_email(email):
            errors.append("Please enter a valid email address.")
        if not valid_phone(phone):
            errors.append("Please enter a valid phone number.")
        if len(enrollment) < 3:
            errors.append("Student ID / enrollment number is required.")
        if not form.get("course"):
            errors.append("Please select your course.")
        if not form.get("year"):
            errors.append("Please select your year / semester.")
        if password != confirm:
            errors.append("Passwords do not match.")
        pw_problem = password_problem(password)
        if pw_problem:
            errors.append(pw_problem)

        if User.query.filter(func.lower(User.email) == email).first():
            errors.append("An account with this email already exists.")
        if Student.query.filter(func.lower(Student.enrollment_no) == enrollment.lower()).first():
            errors.append("This student ID is already registered.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", form=form), 400

        photo = save_upload(request.files.get("photo"), "photos")
        user = User(
            name=name, email=email, phone=phone, role="student", photo=photo,
            created_at=datetime.utcnow(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        student = Student(
            user_id=user.id,
            enrollment_no=enrollment,
            course=form.get("course"),
            department=form.get("department"),
            year=form.get("year"),
            guardian_name=form.get("guardian_name") or None,
            guardian_phone=form.get("guardian_phone") or None,
            address=form.get("address") or None,
        )
        db.session.add(student)
        db.session.flush()

        db.session.add(Notification(
            user_id=user.id,
            title="Welcome to the hostel portal",
            message="Your account is active. Your room will appear here once the warden allocates one.",
            icon="sparkles",
        ))
        db.session.commit()
        log_action("Student registered", entity="student", detail=student.enrollment_no)

        login_user(user)
        session.permanent = True
        flash(f"Welcome, {user.name.split()[0]}! Your account is ready.", "success")
        return redirect(url_for("student.dashboard"))

    return render_template("auth/register.html", form=form)


# --------------------------------------------------------------------------- #
#  Student login
# --------------------------------------------------------------------------- #
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(_home_for(current_user)))

    email = ""
    if request.method == "POST":
        email = clean(request.form.get("email")).lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter(func.lower(User.email) == email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", email=email), 401
        if user.role != "student":
            flash("This is the student portal. Administrators must use the admin login.", "warning")
            return redirect(url_for("auth.admin_login"))
        if not user.is_active:
            flash("This account has been deactivated. Please contact the hostel office.", "danger")
            return render_template("auth/login.html", email=email), 403
        if user.student and user.student.status != "Active":
            flash("Your hostel account is inactive. Please contact the hostel office.", "danger")
            return render_template("auth/login.html", email=email), 403

        login_user(user, remember=remember)
        session.permanent = True
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        log_action("Student signed in", entity="auth", detail=email)
        flash(f"Welcome back, {user.name.split()[0]}!", "success")
        return redirect(_safe_next(request.args.get("next"), url_for("student.dashboard")))

    return render_template("auth/login.html", email=email)


# --------------------------------------------------------------------------- #
#  Admin login
# --------------------------------------------------------------------------- #
@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("admin.overview"))
        flash("You are signed in as a student. Sign out first to use the admin console.", "warning")
        return redirect(url_for("student.dashboard"))

    email = ""
    if request.method == "POST":
        email = clean(request.form.get("email")).lower()
        password = request.form.get("password") or ""
        user = User.query.filter(func.lower(User.email) == email).first()
        if not user or not user.check_password(password):
            flash("Invalid administrator credentials.", "danger")
            return render_template("auth/admin_login.html", email=email), 401
        # The role is verified from the database, never from the submitted form.
        if user.role != "admin":
            flash("This account does not have administrator privileges.", "danger")
            return render_template("auth/admin_login.html", email=email), 403
        if not user.is_active:
            flash("This administrator account is disabled.", "danger")
            return render_template("auth/admin_login.html", email=email), 403

        login_user(user)
        session.permanent = True
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        log_action("Administrator signed in", entity="auth", detail=email)
        flash("Administrator console unlocked.", "success")
        return redirect(_safe_next(request.args.get("next"), url_for("admin.overview")))

    return render_template("auth/admin_login.html", email=email)


# --------------------------------------------------------------------------- #
#  Logout + in-app notifications
# --------------------------------------------------------------------------- #
@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    log_action("Signed out", entity="auth")
    logout_user()
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for("public.home"))


@auth_bp.route("/notifications/read/<int:notif_id>", methods=["POST"])
@login_required
def read_notification(notif_id):
    notif = db.session.get(Notification, notif_id)
    if notif and notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
        if notif.link:
            return redirect(notif.link)
    return redirect(request.referrer or url_for("public.home"))


@auth_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all_notifications():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(request.referrer or url_for("public.home"))
