"""Cross-cutting helpers: auth decorators, validation, uploads, logging, CSV."""
import csv
import io
import os
import re
import secrets
from datetime import date, datetime
from functools import wraps

from flask import abort, current_app, flash, jsonify, redirect, request, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

from .extensions import db
from .models import ActivityLog, Setting, User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^[0-9+\-\s()]{7,20}$")


# --------------------------------------------------------------------------- #
#  Access control
# --------------------------------------------------------------------------- #
def admin_required(fn):
    """Role is always re-read from the database session user - never the form."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.admin_login", next=request.full_path))
        if current_user.role != "admin":
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


def student_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.full_path))
        if current_user.role != "student":
            abort(403)
        student = current_user.student
        if not student:
            flash("Your student profile is incomplete. Contact the hostel office.", "danger")
            return redirect(url_for("auth.logout"))
        if student.status != "Active":
            flash("Your hostel account is inactive. Contact the hostel office.", "danger")
            return redirect(url_for("auth.logout"))
        return fn(*args, **kwargs)

    return wrapper


# --------------------------------------------------------------------------- #
#  Validation
# --------------------------------------------------------------------------- #
def clean(value, max_len=None):
    value = (value or "").strip()
    if max_len:
        value = value[:max_len]
    return value


def valid_email(value):
    return bool(EMAIL_RE.match(value or ""))


def valid_phone(value):
    return bool(PHONE_RE.match(value or ""))


def to_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def to_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_date(value, default=None):
    if not value:
        return default
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return default


def password_problem(password):
    """Poka-yoke: reject weak passwords at the source."""
    if not password or len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain both letters and numbers."
    return None


# --------------------------------------------------------------------------- #
#  Sequencing (human-readable IDs)
# --------------------------------------------------------------------------- #
def next_receipt_no():
    year = date.today().year
    prefix = f"RCPT-{year}-"
    from .models import Payment

    last = (
        db.session.query(Payment.receipt_no)
        .filter(Payment.receipt_no.like(prefix + "%"))
        .order_by(Payment.id.desc())
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last[0].split("-")[-1]) + 1
        except ValueError:
            seq = 1
    return f"{prefix}{seq:05d}"


def next_ticket_no():
    prefix = f"TKT-{date.today().strftime('%y%m')}-"
    from .models import Complaint

    count = db.session.query(Complaint).filter(Complaint.ticket_no.like(prefix + "%")).count()
    return f"{prefix}{count + 1:04d}"


# --------------------------------------------------------------------------- #
#  Uploads (extension whitelist + random name -> no path traversal / overwrite)
# --------------------------------------------------------------------------- #
def save_upload(file_storage, kind="photos", allowed=None):
    if not file_storage or not file_storage.filename:
        return None
    allowed = allowed or current_app.config["ALLOWED_PHOTO_EXT"]
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in allowed:
        return None
    safe = secure_filename(file_storage.filename.rsplit(".", 1)[0])[:40] or "file"
    name = f"{safe}-{secrets.token_hex(6)}.{ext}"
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], kind)
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, name))
    return f"uploads/{kind}/{name}"


def delete_upload(rel_path):
    if not rel_path:
        return
    full = os.path.join(current_app.config["UPLOAD_FOLDER"], rel_path.split("uploads/", 1)[-1])
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass


# --------------------------------------------------------------------------- #
#  Audit trail
# --------------------------------------------------------------------------- #
def log_action(action, entity=None, detail=None):
    try:
        actor = current_user.name if current_user.is_authenticated else "guest"
        uid = current_user.id if current_user.is_authenticated else None
        db.session.add(
            ActivityLog(
                user_id=uid,
                actor=actor,
                action=action[:120],
                entity=entity,
                detail=(detail or "")[:255],
                ip=(request.remote_addr or "")[:60],
            )
        )
        db.session.commit()
    except Exception:  # audit logging must never break a request
        db.session.rollback()


def notify(user_id, title, message="", icon="bell", link=None):
    from .models import Notification

    db.session.add(
        Notification(user_id=user_id, title=title[:140], message=(message or "")[:255],
                     icon=icon, link=link)
    )


# --------------------------------------------------------------------------- #
#  CSV export
# --------------------------------------------------------------------------- #
class CSVResponse:
    @staticmethod
    def build(filename, headers, rows):
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerows(rows)
        payload = "\ufeff" + buf.getvalue()  # BOM keeps Excel happy with ₹
        from flask import Response

        return Response(
            payload,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )


# --------------------------------------------------------------------------- #
#  Template helpers
# --------------------------------------------------------------------------- #
def money(value, symbol="₹"):
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0.0
    whole = f"{abs(value):,.0f}"
    return f"{'-' if value < 0 else ''}{symbol}{whole}"


def short_date(value, fmt="%d %b %Y"):
    if not value:
        return "—"
    return value.strftime(fmt) if hasattr(value, "strftime") else str(value)


def time_ago(value):
    if not value:
        return "—"
    delta = datetime.utcnow() - value
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} hr ago"
    if seconds < 604800:
        return f"{int(seconds // 86400)} d ago"
    return value.strftime("%d %b %Y")


def hostel_setting(key, default=None):
    return Setting.get(key, default)


def wants_json():
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )


def json_ok(message="Done", **extra):
    return jsonify({"ok": True, "message": message, **extra})


def json_err(message="Something went wrong", status=400, **extra):
    return jsonify({"ok": False, "message": message, **extra}), status


def safe_user(email):
    return db.session.query(User).filter(db.func.lower(User.email) == email.lower()).first()
