"""Student portal - a student only ever sees their own data."""
from datetime import date, datetime

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required

from ..extensions import db
from ..models import (ANNOUNCEMENT_TAGS, COMPLAINT_CATEGORIES, Announcement,
                      Complaint, ComplaintResponse, ContactMessage, FeeRecord,
                      Notification, Payment, Setting)
from ..utils import (clean, delete_upload, log_action, next_ticket_no, notify,
                     parse_date, password_problem, save_upload, to_float,
                     valid_email, valid_phone)
from .public import FAQS, RULES

student_bp = Blueprint("student", __name__)


def _student():
    student = current_user.student
    if not student:
        abort(404)
    return student


def _dashboard_stats(student):
    fees = student.fee_records.order_by(FeeRecord.due_date.asc()).all()
    overdue = [f for f in fees if f.balance > 0 and f.due_date and f.due_date < date.today()]
    upcoming = next((f for f in fees if f.balance > 0), None)
    complaints = student.complaints.order_by(Complaint.created_at.desc()).all()
    return {
        "fees": fees,
        "total_billed": round(sum(float(f.amount) for f in fees), 2),
        "total_paid": round(sum(float(p.amount) for p in student.payments), 2),
        "balance": round(sum(f.balance for f in fees), 2),
        "overdue_count": len(overdue),
        "next_due": upcoming,
        "complaints": complaints,
        "open_complaints": sum(1 for c in complaints if c.status in ("Pending", "In Progress")),
        "resolved_complaints": sum(1 for c in complaints if c.status == "Resolved"),
        "payments_count": student.payments.count(),
    }


@student_bp.before_request
@login_required
def guard():
    if current_user.role != "student":
        abort(403)
    student = current_user.student
    if not student:
        flash("Your student profile is incomplete. Contact the hostel office.", "danger")
        return redirect(url_for("auth.logout"))
    if student.status != "Active":
        flash("Your hostel account is inactive. Contact the hostel office.", "danger")
        return redirect(url_for("auth.logout"))
    return None


# --------------------------------------------------------------------------- #
#  Dashboard
# --------------------------------------------------------------------------- #
@student_bp.route("/")
def dashboard():
    student = _student()
    stats = _dashboard_stats(student)
    announcements = (
        Announcement.query.filter_by(is_published=True)
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(3)
        .all()
    )
    allocation = student.active_allocation
    return render_template(
        "student/dashboard.html",
        student=student,
        allocation=allocation,
        room=allocation.room if allocation else None,
        stats=stats,
        announcements=announcements,
        recent_complaints=stats["complaints"][:3],
        recent_payments=student.payments.order_by(Payment.paid_on.desc()).limit(3).all(),
        fee_rows=stats["fees"][:4],
    )


# --------------------------------------------------------------------------- #
#  Profile
# --------------------------------------------------------------------------- #
@student_bp.route("/profile", methods=["GET", "POST"])
def profile():
    student = _student()
    user = current_user
    if request.method == "POST":
        phone = clean(request.form.get("phone"))
        email = clean(request.form.get("email")).lower()
        if not valid_phone(phone):
            flash("Please enter a valid phone number.", "danger")
            return redirect(url_for("student.profile"))
        if email != user.email:
            if not valid_email(email):
                flash("Please enter a valid email address.", "danger")
                return redirect(url_for("student.profile"))
            from ..models import User
            from sqlalchemy import func

            clash = User.query.filter(func.lower(User.email) == email, User.id != user.id).first()
            if clash:
                flash("That email is already used by another account.", "danger")
                return redirect(url_for("student.profile"))
            user.email = email

        user.phone = phone
        student.address = clean(request.form.get("address"))[:255] or None
        student.guardian_name = clean(request.form.get("guardian_name"))[:120] or None
        student.guardian_phone = clean(request.form.get("guardian_phone"))[:20] or None
        db.session.commit()
        log_action("Student updated profile", entity="student", detail=student.enrollment_no)
        flash("Profile updated successfully.", "success")
        return redirect(url_for("student.profile"))

    return render_template("student/profile.html", student=student)


@student_bp.route("/profile/photo", methods=["POST"])
def upload_photo():
    user = current_user
    photo = save_upload(request.files.get("photo"), "photos")
    if not photo:
        flash("Please choose a PNG, JPG or WEBP image (under 4 MB).", "danger")
        return redirect(url_for("student.profile"))
    old = user.photo
    user.photo = photo
    db.session.commit()
    if old and old != photo:
        delete_upload(old)
    log_action("Student updated profile photo", entity="student")
    flash("Profile photo updated.", "success")
    return redirect(url_for("student.profile"))


@student_bp.route("/profile/password", methods=["POST"])
def change_password():
    current = request.form.get("current_password") or ""
    new = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    if not current_user.check_password(current):
        flash("Your current password is incorrect.", "danger")
        return redirect(url_for("student.profile"))
    if new != confirm:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("student.profile"))
    problem = password_problem(new)
    if problem:
        flash(problem, "danger")
        return redirect(url_for("student.profile"))

    current_user.set_password(new)
    db.session.commit()
    log_action("Student changed password", entity="auth")
    flash("Password changed. Use your new password next time you sign in.", "success")
    return redirect(url_for("student.profile"))


# --------------------------------------------------------------------------- #
#  Room
# --------------------------------------------------------------------------- #
@student_bp.route("/room")
def my_room():
    student = _student()
    allocation = student.active_allocation
    history = sorted(
        student.allocations.all(), key=lambda a: a.start_date or date.min, reverse=True
    )
    return render_template(
        "student/room.html",
        student=student,
        allocation=allocation,
        room=allocation.room if allocation else None,
        roommates=student.roommates,
        history=history,
    )


# --------------------------------------------------------------------------- #
#  Fees & payments
# --------------------------------------------------------------------------- #
@student_bp.route("/fees")
def fees():
    student = _student()
    stats = _dashboard_stats(student)
    records = student.fee_records.order_by(FeeRecord.due_date.desc()).all()
    return render_template(
        "student/fees.html", student=student, records=records, stats=stats
    )


@student_bp.route("/payments")
def payments():
    student = _student()
    rows = student.payments.order_by(Payment.paid_on.desc(), Payment.id.desc()).all()
    return render_template(
        "student/payments.html",
        student=student,
        payments=rows,
        total_paid=round(sum(float(p.amount) for p in rows), 2),
        balance=round(sum(f.balance for f in student.fee_records), 2),
    )


@student_bp.route("/payments/<int:payment_id>/receipt")
def receipt(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment or payment.student_id != _student().id:
        abort(404)
    return render_template(
        "student/receipt.html", payment=payment, student=payment.student
    )


# --------------------------------------------------------------------------- #
#  Complaints
# --------------------------------------------------------------------------- #
@student_bp.route("/complaints", methods=["GET", "POST"])
def complaints():
    student = _student()

    if request.method == "POST":
        category = clean(request.form.get("category"))
        subject = clean(request.form.get("subject"))
        description = clean(request.form.get("description"))
        priority = clean(request.form.get("priority")) or "Normal"

        errors = []
        if category not in COMPLAINT_CATEGORIES:
            errors.append("Please choose a valid complaint category.")
        if len(subject) < 5:
            errors.append("Subject must be at least 5 characters long.")
        if len(description) < 15:
            errors.append("Please describe the issue in at least 15 characters.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("student.complaints"))

        attachment = save_upload(
            request.files.get("attachment"), "complaints",
            allowed={"png", "jpg", "jpeg", "webp", "pdf"},
        )
        complaint = Complaint(
            ticket_no=next_ticket_no(),
            student_id=student.id,
            category=category,
            subject=subject[:150],
            description=description[:3000],
            attachment=attachment,
            status="Pending",
            priority=priority if priority in ("Low", "Normal", "High") else "Normal",
        )
        db.session.add(complaint)
        db.session.flush()
        # notify every administrator in-app
        from ..models import User

        for admin in User.query.filter_by(role="admin", is_active_account=True).all():
            notify(
                admin.id,
                f"New {category} complaint from {student.user.name}",
                f"{complaint.ticket_no}: {complaint.subject}",
                icon="megaphone",
                link=url_for("admin.complaint_detail", complaint_id=complaint.id),
            )
        db.session.commit()
        log_action("Complaint submitted", entity="complaint", detail=complaint.ticket_no)
        flash(
            f"Complaint {complaint.ticket_no} submitted. The hostel office has been notified.",
            "success",
        )
        return redirect(url_for("student.complaint_detail", complaint_id=complaint.id))

    status = request.args.get("status", "")
    category = request.args.get("category", "")
    q = clean(request.args.get("q"))
    query = student.complaints
    if status in ("Pending", "In Progress", "Resolved", "Rejected"):
        query = query.filter(Complaint.status == status)
    if category in COMPLAINT_CATEGORIES:
        query = query.filter(Complaint.category == category)
    if q:
        query = query.filter(Complaint.subject.ilike(f"%{q}%"))
    rows = query.order_by(Complaint.created_at.desc()).all()
    counts = {
        s: student.complaints.filter(Complaint.status == s).count()
        for s in ("Pending", "In Progress", "Resolved", "Rejected")
    }
    return render_template(
        "student/complaints.html",
        rows=rows,
        counts=counts,
        categories=COMPLAINT_CATEGORIES,
        status_filter=status,
        category_filter=category,
        q=q,
    )


@student_bp.route("/complaints/<int:complaint_id>")
def complaint_detail(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint or complaint.student_id != _student().id:
        abort(404)
    return render_template(
        "student/complaint_detail.html", complaint=complaint, categories=COMPLAINT_CATEGORIES
    )


@student_bp.route("/complaints/<int:complaint_id>/reply", methods=["POST"])
def complaint_reply(complaint_id):
    complaint = db.session.get(Complaint, complaint_id)
    if not complaint or complaint.student_id != _student().id:
        abort(404)
    if complaint.status == "Rejected":
        flash("This complaint is closed and cannot receive further replies.", "warning")
        return redirect(url_for("student.complaint_detail", complaint_id=complaint.id))
    message = clean(request.form.get("message"))
    if len(message) < 3:
        flash("Please write a short message.", "danger")
        return redirect(url_for("student.complaint_detail", complaint_id=complaint.id))
    db.session.add(ComplaintResponse(
        complaint_id=complaint.id, author_id=current_user.id, message=message[:2000]
    ))
    complaint.updated_at = datetime.utcnow()
    from ..models import User

    for admin in User.query.filter_by(role="admin", is_active_account=True).all():
        notify(admin.id, f"Student replied on {complaint.ticket_no}", message[:120],
               icon="message-square",
               link=url_for("admin.complaint_detail", complaint_id=complaint.id))
    db.session.commit()
    log_action("Student replied on complaint", entity="complaint", detail=complaint.ticket_no)
    flash("Reply sent to the hostel office.", "success")
    return redirect(url_for("student.complaint_detail", complaint_id=complaint.id))


# --------------------------------------------------------------------------- #
#  Announcements / rules / contact
# --------------------------------------------------------------------------- #
@student_bp.route("/announcements")
def announcements():
    tag = request.args.get("tag", "")
    query = Announcement.query.filter_by(is_published=True)
    if tag in ANNOUNCEMENT_TAGS:
        query = query.filter(Announcement.tag == tag)
    rows = query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc()).all()
    return render_template(
        "student/announcements.html", rows=rows, tags=ANNOUNCEMENT_TAGS, tag=tag
    )


@student_bp.route("/rules")
def rules():
    return render_template(
        "student/rules.html", rules=RULES, faqs=FAQS,
        late_fee_note=Setting.get("late_fee_note"),
    )


@student_bp.route("/contact", methods=["GET", "POST"])
def contact():
    student = _student()
    if request.method == "POST":
        subject = clean(request.form.get("subject"))
        message = clean(request.form.get("message"))
        if len(subject) < 4 or len(message) < 10:
            flash("Please add a subject and a message of at least 10 characters.", "danger")
            return redirect(url_for("student.contact"))
        db.session.add(ContactMessage(
            name=student.user.name,
            email=student.user.email,
            phone=student.user.phone,
            subject=subject[:150],
            message=message[:2000],
            source="student",
            student_id=student.id,
        ))
        db.session.commit()
        log_action("Student messaged administration", entity="contact", detail=subject)
        flash("Message sent to the hostel office. Replies arrive at your registered email.", "success")
        return redirect(url_for("student.contact"))

    previous = (
        ContactMessage.query.filter_by(student_id=student.id)
        .order_by(ContactMessage.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "student/contact.html", student=student, previous=previous,
        office_hours=Setting.get("office_hours"), address=Setting.get("address"),
        email=Setting.get("contact_email"), phone=Setting.get("contact_phone"),
    )


# --------------------------------------------------------------------------- #
#  Notifications page (in-app only)
# --------------------------------------------------------------------------- #
@student_bp.route("/notifications")
def notifications():
    rows = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("student/notifications.html", rows=rows)
