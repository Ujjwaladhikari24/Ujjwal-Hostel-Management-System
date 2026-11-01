"""Relational data model for the Hostel Management System.

Tables
------
users, students, rooms, allocations, fee_records, payments,
complaints, complaint_responses, announcements, staff, notifications,
contact_messages, activity_logs, settings

Design notes
------------
* Every money value is stored as Numeric(10, 2) so a move to PostgreSQL is
  a connection-string change, not a rewrite.
* Historical rows (allocations, payments, fee records) are never deleted,
  they are closed / superseded so reports stay accurate.
* Passwords are stored only as Werkzeug hashes.
"""
from datetime import date, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROOM_TYPES = ["Single Sharing", "Double Sharing", "Triple Sharing", "Four Sharing"]
ROOM_TYPE_CAPACITY = {
    "Single Sharing": 1,
    "Double Sharing": 2,
    "Triple Sharing": 3,
    "Four Sharing": 4,
}
COMPLAINT_CATEGORIES = [
    "Electricity",
    "Water Supply",
    "Cleaning",
    "Food Quality",
    "Wi-Fi",
    "Room Maintenance",
    "Security",
    "Other",
]
COMPLAINT_STATUSES = ["Pending", "In Progress", "Resolved", "Rejected"]
PAYMENT_METHODS = ["Cash", "UPI", "Bank Transfer", "Other"]
STAFF_ROLES = [
    "Warden",
    "Assistant Warden",
    "Security Staff",
    "Cleaning Staff",
    "Maintenance Staff",
    "Mess Manager",
]
ANNOUNCEMENT_TAGS = ["General", "Maintenance", "Fees", "Event", "Holiday", "Mess"]


# --------------------------------------------------------------------------- #
#  Users / students
# --------------------------------------------------------------------------- #
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", index=True)
    photo = db.Column(db.String(255))
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    student = db.relationship(
        "Student", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    # Flask-Login uses `is_active`
    @property
    def is_active(self):  # noqa: D401  (Flask-Login contract)
        return bool(self.is_active_account)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw or "")

    @property
    def initials(self):
        parts = [p for p in (self.name or "").split() if p]
        return ("".join(p[0] for p in parts[:2]) or "U").upper()

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_student(self):
        return self.role == "student"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    enrollment_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    course = db.Column(db.String(80))
    department = db.Column(db.String(80))
    year = db.Column(db.String(20))
    guardian_name = db.Column(db.String(120))
    guardian_phone = db.Column(db.String(20))
    address = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default="Active")  # Active / Inactive
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", back_populates="student")
    allocations = db.relationship(
        "Allocation", back_populates="student", lazy="dynamic", cascade="all, delete-orphan"
    )
    fee_records = db.relationship("FeeRecord", back_populates="student", lazy="dynamic")
    payments = db.relationship("Payment", back_populates="student", lazy="dynamic")
    complaints = db.relationship("Complaint", back_populates="student", lazy="dynamic")

    # -- allocation helpers ------------------------------------------------
    @property
    def active_allocation(self):
        return (
            self.allocations.filter_by(is_active=True)
            .order_by(Allocation.id.desc())
            .first()
        )

    @property
    def room(self):
        alloc = self.active_allocation
        return alloc.room if alloc else None

    @property
    def roommates(self):
        alloc = self.active_allocation
        if not alloc:
            return []
        return [
            a.student
            for a in alloc.room.active_allocations
            if a.student_id != self.id
        ]

    # -- money helpers -----------------------------------------------------
    @property
    def total_billed(self):
        return float(sum((f.amount for f in self.fee_records), 0) or 0)

    @property
    def total_paid(self):
        return float(sum((p.amount for p in self.payments), 0) or 0)

    @property
    def balance(self):
        return round(self.total_billed - self.total_paid, 2)

    @property
    def next_due(self):
        return (
            self.fee_records.filter(FeeRecord.amount > 0)
            .order_by(FeeRecord.due_date.asc())
            .all()
        )

    @property
    def fee_status(self):
        if self.balance <= 0 and self.total_billed > 0:
            return "Paid"
        if self.total_paid > 0:
            return "Partial"
        return "Pending"

    def __repr__(self):
        return f"<Student {self.enrollment_no}>"


# --------------------------------------------------------------------------- #
#  Rooms & allocations
# --------------------------------------------------------------------------- #
class Room(db.Model):
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    block = db.Column(db.String(40))
    floor = db.Column(db.Integer, nullable=False, default=0)
    room_type = db.Column(db.String(40), nullable=False, default="Double Sharing")
    capacity = db.Column(db.Integer, nullable=False, default=2)
    fee_per_semester = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="Available")
    # Available | Maintenance | Archived
    amenities = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    allocations = db.relationship(
        "Allocation", back_populates="room", lazy="dynamic", cascade="all, delete-orphan"
    )

    @property
    def active_allocations(self):
        return self.allocations.filter_by(is_active=True).all()

    @property
    def occupied_beds(self):
        return len(self.active_allocations)

    @property
    def free_beds(self):
        return max(self.capacity - self.occupied_beds, 0)

    @property
    def occupancy_pct(self):
        if not self.capacity:
            return 0
        return round(self.occupied_beds * 100 / self.capacity)

    @property
    def live_status(self):
        """Status derived from real allocations (never fabricated)."""
        if self.status in ("Maintenance", "Archived"):
            return self.status
        if self.occupied_beds == 0:
            return "Available"
        if self.occupied_beds >= self.capacity:
            return "Full"
        return "Partially Occupied"

    @property
    def status_class(self):
        return {
            "Available": "ok",
            "Partially Occupied": "warn",
            "Full": "info",
            "Maintenance": "danger",
            "Archived": "muted",
        }.get(self.live_status, "muted")

    @property
    def free_bed_numbers(self):
        taken = {a.bed_number for a in self.active_allocations}
        return [n for n in range(1, self.capacity + 1) if n not in taken]

    def __repr__(self):
        return f"<Room {self.room_number}>"


class Allocation(db.Model):
    __tablename__ = "allocations"
    __table_args__ = (
        db.Index("ix_alloc_room_active", "room_id", "is_active"),
        db.Index("ix_alloc_student_active", "student_id", "is_active"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    room_id = db.Column(
        db.Integer, db.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    bed_number = db.Column(db.Integer, nullable=False, default=1)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship("Student", back_populates="allocations")
    room = db.relationship("Room", back_populates="allocations")

    def __repr__(self):
        return f"<Allocation s{self.student_id} -> r{self.room_id} bed{self.bed_number}>"


# --------------------------------------------------------------------------- #
#  Fees & payments
# --------------------------------------------------------------------------- #
class FeeRecord(db.Model):
    __tablename__ = "fee_records"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    due_date = db.Column(db.Date, nullable=False, default=date.today)
    semester = db.Column(db.String(40))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    student = db.relationship("Student", back_populates="fee_records")
    payments = db.relationship("Payment", back_populates="fee_record", lazy="select")

    @property
    def paid_amount(self):
        return round(float(sum((p.amount for p in self.payments), 0) or 0), 2)

    @property
    def balance(self):
        return round(float(self.amount) - self.paid_amount, 2)

    @property
    def status(self):
        if self.balance <= 0:
            return "Paid"
        if self.paid_amount > 0:
            return "Partial"
        if self.due_date and self.due_date < date.today():
            return "Overdue"
        return "Pending"

    @property
    def status_class(self):
        return {
            "Paid": "ok",
            "Partial": "warn",
            "Pending": "info",
            "Overdue": "danger",
        }[self.status]

    def __repr__(self):
        return f"<FeeRecord {self.title} {self.amount}>"


class Payment(db.Model):
    """A payment *recorded by an administrator* (cash / UPI / transfer).

    There is no payment gateway integration in this project, so every row in
    this table was entered manually by an authorised admin - the UI says so
    explicitly instead of pretending an online payment happened.
    """
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    receipt_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    fee_record_id = db.Column(db.Integer, db.ForeignKey("fee_records.id"))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_on = db.Column(db.Date, nullable=False, default=date.today)
    method = db.Column(db.String(30), nullable=False, default="Cash")
    reference = db.Column(db.String(80))
    note = db.Column(db.String(255))
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    student = db.relationship("Student", back_populates="payments")
    fee_record = db.relationship("FeeRecord", back_populates="payments")
    recorder = db.relationship("User", foreign_keys=[recorded_by])

    def __repr__(self):
        return f"<Payment {self.receipt_no} {self.amount}>"


# --------------------------------------------------------------------------- #
#  Complaints
# --------------------------------------------------------------------------- #
class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    ticket_no = db.Column(db.String(30), unique=True, nullable=False, index=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    category = db.Column(db.String(40), nullable=False, default="Other", index=True)
    subject = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    attachment = db.Column(db.String(255))
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    priority = db.Column(db.String(20), nullable=False, default="Normal")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    handled_by = db.Column(db.Integer, db.ForeignKey("users.id"))

    student = db.relationship("Student", back_populates="complaints")
    responses = db.relationship(
        "ComplaintResponse",
        back_populates="complaint",
        cascade="all, delete-orphan",
        order_by="ComplaintResponse.created_at",
    )

    @property
    def status_class(self):
        return {
            "Pending": "warn",
            "In Progress": "info",
            "Resolved": "ok",
            "Rejected": "danger",
        }[self.status]

    @property
    def resolution_hours(self):
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.created_at
        return round(delta.total_seconds() / 3600, 1)

    def __repr__(self):
        return f"<Complaint {self.ticket_no} {self.status}>"


class ComplaintResponse(db.Model):
    __tablename__ = "complaint_responses"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(
        db.Integer, db.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    complaint = db.relationship("Complaint", back_populates="responses")
    author = db.relationship("User")


# --------------------------------------------------------------------------- #
#  Announcements / notifications / staff / misc
# --------------------------------------------------------------------------- #
class Announcement(db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(30), nullable=False, default="General")
    is_published = db.Column(db.Boolean, nullable=False, default=True, index=True)
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)
    posted_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    author = db.relationship("User")

    def __repr__(self):
        return f"<Announcement {self.title}>"


class Notification(db.Model):
    """In-app notification only - no email/SMS service is wired up."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = db.Column(db.String(140), nullable=False)
    message = db.Column(db.String(255))
    icon = db.Column(db.String(30), default="bell")
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User")


class Staff(db.Model):
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(40), nullable=False, default="Warden")
    phone = db.Column(db.String(20))
    email = db.Column(db.String(190))
    shift = db.Column(db.String(40))
    joined_on = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(20), nullable=False, default="Active")
    notes = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def initials(self):
        parts = [p for p in (self.full_name or "").split() if p]
        return ("".join(p[0] for p in parts[:2]) or "S").upper()


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(190), nullable=False)
    phone = db.Column(db.String(20))
    subject = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(20), default="public")  # public | student
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ActivityLog(db.Model):
    """Lightweight audit trail (TQM: traceability / Q04 audit trail)."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor = db.Column(db.String(120))
    action = db.Column(db.String(120), nullable=False)
    entity = db.Column(db.String(60))
    detail = db.Column(db.String(255))
    ip = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User")


class Setting(db.Model):
    """Key/value singleton settings (hostel profile, fee defaults, toggles)."""

    __tablename__ = "settings"

    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.String(255))

    DEFAULT = {
        "hostel_name": "Ujjwal Hostel",
        "hostel_tagline": "Smart Hostel Management. Comfortable Living. Better Experiences.",
        "address": "Block C, University Campus, Jaipur, Rajasthan 302017",
        "contact_email": "office@ujjwalhostel.edu.in",
        "contact_phone": "+91 141 400 7788",
        "office_hours": "Mon – Sat, 9:00 AM – 5:30 PM",
        "academic_session": "2026–27",
        "default_fee": "48000",
        "late_fee_note": "A late fee of ₹500 applies after the due date.",
        "registration_open": "1",
    }

    @classmethod
    def get(cls, key, default=None):
        row = db.session.get(cls, key)
        if row:
            return row.value
        return cls.DEFAULT.get(key, default)

    @classmethod
    def get_bool(cls, key, default=False):
        val = cls.get(key)
        if val is None:
            return default
        return str(val).strip() in {"1", "true", "yes", "on"}

    @classmethod
    def set(cls, key, value):
        row = db.session.get(cls, key)
        if row:
            row.value = "" if value is None else str(value)
        else:
            db.session.add(cls(key=key, value="" if value is None else str(value)))


class PDCALog(db.Model):
    """PDCA improvement log used by the Quality (TQM) screen."""

    __tablename__ = "pdca_logs"

    id = db.Column(db.Integer, primary_key=True)
    phase = db.Column(db.String(10), nullable=False, default="Plan")  # Plan/Do/Check/Act
    title = db.Column(db.String(150), nullable=False)
    detail = db.Column(db.Text)
    owner = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class DefectLog(db.Model):
    """Checksheet / defect log for SQC reporting (category + severity + status)."""

    __tablename__ = "defect_logs"

    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="Software Code")
    severity = db.Column(db.Integer, nullable=False, default=3)
    occurrence = db.Column(db.Integer, nullable=False, default=3)
    detection = db.Column(db.Integer, nullable=False, default=3)
    status = db.Column(db.String(20), nullable=False, default="Open")
    logged_on = db.Column(db.Date, nullable=False, default=date.today)

    @property
    def rpn(self):
        return self.severity * self.occurrence * self.detection
