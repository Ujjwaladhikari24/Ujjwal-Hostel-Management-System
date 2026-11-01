"""Public marketing site: landing page + public contact form.

Every number shown on the landing page comes from the live database
(rooms, beds, allocations) - nothing is hardcoded marketing fluff.
"""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import Announcement, ContactMessage, Room, ROOM_TYPES, Setting, Staff, Student
from ..utils import clean, log_action, valid_email

public_bp = Blueprint("public", __name__)

FACILITIES = [
    ("wifi", "Fibre Wi-Fi", "1 Gbps campus network with per-room access points.", "#4f46e5"),
    ("utensils", "Mess & Dining", "Four meals a day, menu rotated weekly by the mess committee.", "#f97316"),
    ("book-open", "Study Hall", "Silent reading room open 24×7 during examination weeks.", "#06b6d4"),
    ("shield-check", "24×7 Security", "Biometric entry, CCTV coverage and resident wardens.", "#7c3aed"),
    ("washing-machine", "Laundry", "Two washing zones with scheduled pick-up slots.", "#0ea5e9"),
    ("heart-pulse", "Medical Support", "On-call doctor, first-aid room and campus ambulance.", "#ef4444"),
    ("dumbbell", "Sports & Gym", "Gym, indoor games and a floodlit court.", "#10b981"),
    ("wrench", "Maintenance Desk", "In-app complaints routed to the maintenance team.", "#f59e0b"),
]

RULES = [
    ("Entry & Exit", "Residents must be inside the hostel by 9:30 PM. Late entry is logged at the security desk."),
    ("Visitors", "Visitors are allowed in the common lounge between 10:00 AM and 6:00 PM with a gate pass."),
    ("Room Care", "Keep rooms clean; damage to furniture or fittings is charged to the resident."),
    ("Electrical Safety", "Use of heaters, induction plates or high-wattage appliances is prohibited."),
    ("Quiet Hours", "Quiet hours run from 10:00 PM to 6:00 AM in corridors and study areas."),
    ("Fees", "Semester fees must be paid by the notified due date to avoid late charges."),
    ("Complaints", "Register complaints through the student portal; urgent issues go directly to the duty warden."),
    ("Anti-Ragging", "The hostel follows a strict zero-tolerance anti-ragging policy."),
]

FAQS = [
    ("Who can apply for hostel accommodation?",
     "Any student of the university with a valid enrollment number can register on this portal and request accommodation. The warden allocates rooms based on availability and the student's year of study."),
    ("How is the hostel fee calculated?",
     "Each room type has a semester fee set by the administration. Fees are assigned to your account by the hostel office and appear in Fee Details with the due date."),
    ("Can I pay the fee online?",
     "This portal does not connect to a payment gateway. Payments made at the hostel office (cash, UPI or bank transfer) are recorded by the administration and appear in your payment history with a receipt number."),
    ("How do I raise a complaint?",
     "Open Submit Complaint in the student portal, choose a category, describe the issue and attach a photo if useful. You can track the status and read the warden's response on the same page."),
    ("What happens if my room is at full capacity?",
     "The system blocks any allocation that would exceed a room's bed capacity, so over-allocation cannot happen."),
    ("Can I change my room after allocation?",
     "Room changes are handled by the warden. Submit a complaint under Room Maintenance or contact the hostel office; the warden can reassign your bed from Room Allocation."),
]


def _room_overview():
    """Aggregate real room/bed availability per room type."""
    rows = []
    rooms = Room.query.filter(Room.status != "Archived").all()
    for rtype in ROOM_TYPES:
        group = [r for r in rooms if r.room_type == rtype]
        if not group:
            continue
        # Beds inside rooms under maintenance are not allocatable, so they are
        # left out of capacity/free figures — this keeps the public numbers
        # identical to the administrator dashboard.
        capacity = sum(r.capacity for r in group if r.live_status != "Maintenance")
        occupied = sum(r.occupied_beds for r in group)
        fees = [float(r.fee_per_semester or 0) for r in group if r.fee_per_semester]
        rows.append({
            "type": rtype,
            "rooms": len(group),
            "capacity": capacity,
            "occupied": occupied,
            "free": max(capacity - occupied, 0),
            "fee_min": min(fees) if fees else 0,
            "fee_max": max(fees) if fees else 0,
            "maintenance": sum(1 for r in group if r.live_status == "Maintenance"),
        })
    total_capacity = sum(r["capacity"] for r in rows)
    total_free = sum(r["free"] for r in rows)
    total_occupied = sum(r["occupied"] for r in rows)
    return {
        "types": rows,
        "rooms": len(rooms),
        "capacity": total_capacity,
        "occupied": total_occupied,
        "free": total_free,
        "occupancy_pct": round(total_occupied * 100 / total_capacity) if total_capacity else 0,
    }


@public_bp.route("/")
def home():
    overview = _room_overview()
    announcements = (
        Announcement.query.filter_by(is_published=True)
        .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .limit(3)
        .all()
    )
    stats = {
        "residents": Student.query.filter(Student.status == "Active").count(),
        "rooms": overview["rooms"],
        "free_beds": overview["free"],
        "staff": Staff.query.filter_by(status="Active").count(),
        "wardens": Staff.query.filter(Staff.status == "Active", Staff.role.in_(["Warden", "Assistant Warden"])).count(),
    }
    return render_template(
        "public/home.html",
        overview=overview,
        announcements=announcements,
        facilities=FACILITIES,
        rules=RULES,
        faqs=FAQS,
        stats=stats,
        hostel_name=Setting.get("hostel_name"),
        registration_open=Setting.get_bool("registration_open", True),
    )


@public_bp.route("/contact", methods=["POST"])
def contact():
    form = {k: clean(v) for k, v in request.form.items()}
    name, email = form.get("name", ""), form.get("email", "").lower()
    subject, message = form.get("subject", ""), form.get("message", "")

    if not name or not valid_email(email) or len(message) < 10:
        flash("Please share your name, a valid email and a message of at least 10 characters.", "danger")
        return redirect(url_for("public.home") + "#contact")

    db.session.add(ContactMessage(
        name=name[:120], email=email[:190], phone=form.get("phone", "")[:20],
        subject=subject[:150] or "General enquiry", message=message[:2000], source="public",
    ))
    db.session.commit()
    log_action("Public contact message received", entity="contact", detail=email)
    flash("Thanks! Your message has reached the hostel office. We reply on working days.", "success")
    return redirect(url_for("public.home") + "#contact")
