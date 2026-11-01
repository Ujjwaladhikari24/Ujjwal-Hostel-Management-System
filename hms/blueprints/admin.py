"""Administrator console: students, rooms, allocations, fees, payments,
complaints, announcements, staff, reports, quality (TQM) and settings."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user
from sqlalchemy import func, or_

from ..extensions import db
from ..models import (ANNOUNCEMENT_TAGS, COMPLAINT_CATEGORIES, COMPLAINT_STATUSES,
                      ActivityLog,
                      PAYMENT_METHODS, ROOM_TYPES, ROOM_TYPE_CAPACITY, STAFF_ROLES,
                      Allocation, Announcement, Complaint, ComplaintResponse,
                      ContactMessage, DefectLog, FeeRecord, Notification,
                      PDCALog, Payment, Room, Setting, Staff, Student, User)
from ..utils import (CSVResponse, admin_required, clean, log_action, next_receipt_no,
                     notify, parse_date, password_problem, to_float, to_int,
                     valid_email, valid_phone)

admin_bp = Blueprint("admin", __name__)


@admin_bp.before_request
@admin_required
def guard():
    return None


def _paginate(query, per_page=None):
    per_page = per_page or 12
    page = max(to_int(request.args.get("page"), 1), 1)
    total = query.count()
    rows = query.limit(per_page).offset((page - 1) * per_page).all()
    pages = max((total + per_page - 1) // per_page, 1)
    return rows, {"page": page, "pages": pages, "total": total, "per_page": per_page}


def _core_stats():
    students = Student.query.all()
    rooms = Room.query.filter(Room.status != "Archived").all()
    active_students = [s for s in students if s.status == "Active"]
    capacity = sum(r.capacity for r in rooms if r.live_status != "Maintenance")
    occupied = sum(r.occupied_beds for r in rooms)
    billed = float(db.session.query(func.coalesce(func.sum(FeeRecord.amount), 0)).scalar() or 0)
    collected = float(db.session.query(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0)
    complaints = Complaint.query.all()
    return {
        "students": len(active_students),
        "students_total": len(students),
        "unallocated": sum(1 for s in active_students if not s.active_allocation),
        "rooms": len(rooms),
        "capacity": capacity,
        "occupied_beds": occupied,
        "free_beds": max(capacity - occupied, 0),
        "occupancy_pct": round(occupied * 100 / capacity) if capacity else 0,
        "full_rooms": sum(1 for r in rooms if r.live_status == "Full"),
        "available_rooms": sum(1 for r in rooms if r.live_status == "Available"),
        "maintenance_rooms": sum(1 for r in rooms if r.live_status == "Maintenance"),
        "billed": round(billed, 2),
        "collected": round(collected, 2),
        "outstanding": round(max(billed - collected, 0), 2),
        "collection_pct": round(collected * 100 / billed) if billed else 0,
        "students_with_dues": sum(1 for s in active_students if s.balance > 0),
        "complaints_total": len(complaints),
        "complaints_pending": sum(1 for c in complaints if c.status == "Pending"),
        "complaints_progress": sum(1 for c in complaints if c.status == "In Progress"),
        "complaints_resolved": sum(1 for c in complaints if c.status == "Resolved"),
        "complaints_rejected": sum(1 for c in complaints if c.status == "Rejected"),
        "staff": Staff.query.filter_by(status="Active").count(),
        "announcements": Announcement.query.filter_by(is_published=True).count(),
    }


def _month_series(months=6):
    """Fee collection per month from real payment rows."""
    today = date.today()
    labels, collected, billed = [], [], []
    for i in range(months - 1, -1, -1):
        y, m = today.year, today.month - i
        while m <= 0:
            m += 12
            y -= 1
        start = date(y, m, 1)
        end = date(y + (m == 12), (m % 12) + 1, 1)
        amount = float(
            db.session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.paid_on >= start, Payment.paid_on < end)
            .scalar() or 0
        )
        due = float(
            db.session.query(func.coalesce(func.sum(FeeRecord.amount), 0))
            .filter(FeeRecord.due_date >= start, FeeRecord.due_date < end)
            .scalar() or 0
        )
        labels.append(start.strftime("%b %Y"))
        collected.append(round(amount, 2))
        billed.append(round(due, 2))
    return labels, collected, billed


# --------------------------------------------------------------------------- #
#  Overview
# --------------------------------------------------------------------------- #
@admin_bp.route("/")
def overview():
    stats = _core_stats()
    labels, collected, billed = _month_series(6)

    rooms = Room.query.filter(Room.status != "Archived").all()
    type_labels, type_capacity, type_occupied = [], [], []
    for rtype in ROOM_TYPES:
        group = [r for r in rooms if r.room_type == rtype]
        if not group:
            continue
        type_labels.append(rtype.replace(" Sharing", ""))
        type_capacity.append(sum(r.capacity for r in group))
        type_occupied.append(sum(r.occupied_beds for r in group))

    complaint_counts = {
        s: Complaint.query.filter_by(status=s).count() for s in COMPLAINT_STATUSES
    }

    recent_complaints = (
        Complaint.query.order_by(Complaint.created_at.desc()).limit(6).all()
    )
    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(6).all()
    recent_activity = (
        ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(8).all()
    )
    upcoming_dues = (
        FeeRecord.query.filter(FeeRecord.due_date >= date.today())
        .order_by(FeeRecord.due_date.asc())
        .limit(5)
        .all()
    )
    room_status_counts = Counter(r.live_status for r in rooms)

    return render_template(
        "admin/overview.html",
        stats=stats,
        month_labels=labels,
        month_collected=collected,
        month_billed=billed,
        type_labels=type_labels,
        type_capacity=type_capacity,
        type_occupied=type_occupied,
        complaint_counts=complaint_counts,
        complaint_labels=list(complaint_counts.keys()),
        complaint_values=list(complaint_counts.values()),
        recent_complaints=recent_complaints,
        recent_payments=recent_payments,
        recent_activity=recent_activity,
        upcoming_dues=upcoming_dues,
        room_status_counts=room_status_counts,
        tabs="overview",
    )


@admin_bp.route("/activity")
def activity():
    rows, page = _paginate(ActivityLog.query.order_by(ActivityLog.created_at.desc()), 25)
    return render_template("admin/activity.html", rows=rows, page=page)


# --------------------------------------------------------------------------- #
#  Students
# --------------------------------------------------------------------------- #
@admin_bp.route("/students")
def students():
    q = clean(request.args.get("q"))
    status = request.args.get("status", "")
    year = request.args.get("year", "")
    housed = request.args.get("housed", "")

    query = Student.query.join(User)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            User.name.ilike(like), User.email.ilike(like), User.phone.ilike(like),
            Student.enrollment_no.ilike(like), Student.course.ilike(like),
            Student.department.ilike(like),
        ))
    if status in ("Active", "Inactive"):
        query = query.filter(Student.status == status)
    if year:
        query = query.filter(Student.year == year)
    rows, page = _paginate(query.order_by(User.name.asc()), 15)
    if housed == "no":
        rows = [s for s in rows if not s.active_allocation]
    elif housed == "yes":
        rows = [s for s in rows if s.active_allocation]

    years = sorted({s.year for s in Student.query.all() if s.year})
    return render_template(
        "admin/students.html", rows=rows, page=page, q=q, status=status, year=year,
        housed=housed, years=years,
    )


@admin_bp.route("/students/new", methods=["GET", "POST"])
def student_new():
    form = {}
    if request.method == "POST":
        form = {k: clean(v) for k, v in request.form.items()}
        errors = []
        email = form.get("email", "").lower()
        enrollment = form.get("enrollment_no", "").upper()
        password = request.form.get("password") or ""

        if len(form.get("name", "")) < 3:
            errors.append("Full name is required.")
        if not valid_email(email):
            errors.append("A valid email is required.")
        if not valid_phone(form.get("phone", "")):
            errors.append("A valid phone number is required.")
        if len(enrollment) < 3:
            errors.append("Enrollment number is required.")
        if not password:
            password = "Hostel@123"
            flash("No password supplied - the default password Hostel@123 was set.", "warning")
        problem = password_problem(password)
        if problem:
            errors.append(problem)
        if User.query.filter(func.lower(User.email) == email).first():
            errors.append("This email is already registered.")
        if Student.query.filter(func.lower(Student.enrollment_no) == enrollment.lower()).first():
            errors.append("This enrollment number already exists.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/student_form.html", form=form, rooms=_room_choices()), 400

        user = User(name=form["name"], email=email, phone=form.get("phone"),
                    role="student", created_at=datetime.utcnow())
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        student = Student(
            user_id=user.id, enrollment_no=enrollment, course=form.get("course"),
            department=form.get("department"), year=form.get("year"),
            guardian_name=form.get("guardian_name") or None,
            guardian_phone=form.get("guardian_phone") or None,
            address=form.get("address") or None,
        )
        db.session.add(student)
        db.session.flush()

        room_id = to_int(form.get("room_id"))
        if room_id:
            room = db.session.get(Room, room_id)
            error = _assign(student, room, to_int(form.get("bed_number")) or None, "Initial allocation")
            if error:
                flash(error, "warning")
            else:
                flash(f"Student allocated to room {room.room_number}.", "success")

        notify(user.id, "Welcome to the hostel portal",
               "Your account was created by the hostel office.", icon="user-plus")
        db.session.commit()
        log_action("Student created", entity="student", detail=enrollment)
        flash(f"{user.name} added successfully.", "success")
        return redirect(url_for("admin.student_detail", student_id=student.id))

    return render_template("admin/student_form.html", form=form, rooms=_room_choices())


@admin_bp.route("/students/<int:student_id>")
def student_detail(student_id):
    student = db.session.get(Student, student_id) or abort(404)
    fees = student.fee_records.order_by(FeeRecord.due_date.desc()).all()
    return render_template(
        "admin/student_detail.html",
        student=student,
        fees=fees,
        payments=student.payments.order_by(Payment.paid_on.desc()).all(),
        complaints=student.complaints.order_by(Complaint.created_at.desc()).all(),
        allocations=sorted(student.allocations.all(), key=lambda a: a.start_date or date.min, reverse=True),
        rooms=_room_choices(),
        balance=round(sum(f.balance for f in fees), 2),
        billed=round(sum(float(f.amount) for f in fees), 2),
        paid=round(sum(float(p.amount) for p in student.payments), 2),
    )


@admin_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def student_edit(student_id):
    student = db.session.get(Student, student_id) or abort(404)
    user = student.user
    form = {
        "name": user.name, "email": user.email, "phone": user.phone or "",
        "enrollment_no": student.enrollment_no, "course": student.course or "",
        "department": student.department or "", "year": student.year or "",
        "guardian_name": student.guardian_name or "",
        "guardian_phone": student.guardian_phone or "", "address": student.address or "",
        "status": student.status,
    }
    if request.method == "POST":
        form = {k: clean(v) for k, v in request.form.items()}
        email = form.get("email", "").lower()
        enrollment = form.get("enrollment_no", "").upper()
        errors = []
        if len(form.get("name", "")) < 3:
            errors.append("Full name is required.")
        if not valid_email(email):
            errors.append("A valid email is required.")
        if User.query.filter(func.lower(User.email) == email, User.id != user.id).first():
            errors.append("Another account already uses this email.")
        if Student.query.filter(func.lower(Student.enrollment_no) == enrollment.lower(),
                                Student.id != student.id).first():
            errors.append("Another student already uses this enrollment number.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/student_form.html", form=form, student=student,
                                   rooms=_room_choices()), 400

        user.name, user.email = form["name"], email
        user.phone = form.get("phone")
        student.enrollment_no = enrollment
        student.course = form.get("course")
        student.department = form.get("department")
        student.year = form.get("year")
        student.guardian_name = form.get("guardian_name") or None
        student.guardian_phone = form.get("guardian_phone") or None
        student.address = form.get("address") or None
        if form.get("status") in ("Active", "Inactive"):
            student.status = form["status"]
        if request.form.get("toggle_account") == "1":
            user.is_active_account = not user.is_active_account
        db.session.commit()
        log_action("Student updated", entity="student", detail=enrollment)
        flash("Student record updated.", "success")
        return redirect(url_for("admin.student_detail", student_id=student.id))

    return render_template("admin/student_form.html", form=form, student=student,
                           rooms=_room_choices())


@admin_bp.route("/students/<int:student_id>/toggle", methods=["POST"])
def student_toggle(student_id):
    student = db.session.get(Student, student_id) or abort(404)
    student.status = "Inactive" if student.status == "Active" else "Active"
    student.user.is_active_account = student.status == "Active"
    db.session.commit()
    log_action(f"Student marked {student.status}", entity="student",
               detail=student.enrollment_no)
    flash(f"{student.user.name} is now {student.status.lower()}.", "success")
    return redirect(request.referrer or url_for("admin.students"))


@admin_bp.route("/students/<int:student_id>/delete", methods=["POST"])
def student_delete(student_id):
    student = db.session.get(Student, student_id) or abort(404)
    if student.payments.count() or student.fee_records.count():
        flash(
            "This student has fee or payment history, which must be preserved. "
            "Deactivate the account instead of deleting it.",
            "danger",
        )
        return redirect(url_for("admin.student_detail", student_id=student.id))
    name = student.user.name
    for alloc in student.allocations.filter_by(is_active=True).all():
        alloc.is_active, alloc.end_date = False, date.today()
    db.session.delete(student.user)
    db.session.commit()
    log_action("Student deleted", entity="student", detail=name)
    flash(f"{name} was removed from the system.", "success")
    return redirect(url_for("admin.students"))


@admin_bp.route("/students/<int:student_id>/reset-password", methods=["POST"])
def student_reset_password(student_id):
    student = db.session.get(Student, student_id) or abort(404)
    new = request.form.get("new_password") or ""
    problem = password_problem(new)
    if problem:
        flash(problem, "danger")
        return redirect(url_for("admin.student_detail", student_id=student.id))
    student.user.set_password(new)
    notify(student.user.id, "Password reset by the hostel office",
           "Your password was reset by an administrator.", icon="key-round")
    db.session.commit()
    log_action("Student password reset", entity="student", detail=student.enrollment_no)
    flash(f"Password updated for {student.user.name}.", "success")
    return redirect(url_for("admin.student_detail", student_id=student.id))


# --------------------------------------------------------------------------- #
#  Rooms
# --------------------------------------------------------------------------- #
def _room_choices():
    rooms = Room.query.filter(Room.status != "Archived").order_by(Room.room_number).all()
    return [r for r in rooms if r.free_beds > 0 and r.live_status != "Maintenance"]


@admin_bp.route("/rooms")
def rooms():
    q = clean(request.args.get("q"))
    rtype = request.args.get("type", "")
    status = request.args.get("status", "")
    floor = request.args.get("floor", "")

    query = Room.query.filter(Room.status != "Archived")
    if q:
        query = query.filter(or_(Room.room_number.ilike(f"%{q}%"), Room.block.ilike(f"%{q}%")))
    if rtype in ROOM_TYPES:
        query = query.filter(Room.room_type == rtype)
    if floor:
        query = query.filter(Room.floor == to_int(floor))
    rows = query.order_by(Room.block, Room.floor, Room.room_number).all()
    if status:
        rows = [r for r in rows if r.live_status == status]

    all_rooms = Room.query.filter(Room.status != "Archived").all()
    summary = {
        "rooms": len(all_rooms),
        "beds": sum(r.capacity for r in all_rooms),
        "occupied": sum(r.occupied_beds for r in all_rooms),
        "free": sum(r.free_beds for r in all_rooms),
        "available": sum(1 for r in all_rooms if r.live_status == "Available"),
        "full": sum(1 for r in all_rooms if r.live_status == "Full"),
        "partial": sum(1 for r in all_rooms if r.live_status == "Partially Occupied"),
        "maintenance": sum(1 for r in all_rooms if r.live_status == "Maintenance"),
    }
    floors = sorted({r.floor for r in all_rooms})
    blocks = sorted({r.block for r in all_rooms if r.block})
    return render_template(
        "admin/rooms.html", rows=rows, summary=summary, q=q, rtype=rtype, status=status,
        floor=floor, floors=floors, blocks=blocks, room_types=ROOM_TYPES,
    )


@admin_bp.route("/rooms/new", methods=["GET", "POST"])
def room_new():
    form = {}
    if request.method == "POST":
        form = {k: clean(v) for k, v in request.form.items()}
        number = form.get("room_number", "").upper()
        rtype = form.get("room_type", "Double Sharing")
        errors = []
        if not number:
            errors.append("Room number is required.")
        if Room.query.filter(func.lower(Room.room_number) == number.lower()).first():
            errors.append("A room with this number already exists.")
        if rtype not in ROOM_TYPES:
            errors.append("Please choose a valid room type.")
        capacity = to_int(form.get("capacity"), ROOM_TYPE_CAPACITY.get(rtype, 2))
        if not 1 <= capacity <= 8:
            errors.append("Bed capacity must be between 1 and 8.")
        if to_float(form.get("fee_per_semester")) <= 0:
            errors.append("Semester fee must be greater than zero.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/room_form.html", form=form,
                                   room_types=ROOM_TYPES, room=None), 400

        room = Room(
            room_number=number, block=form.get("block") or None,
            floor=to_int(form.get("floor")), room_type=rtype, capacity=capacity,
            fee_per_semester=to_float(form.get("fee_per_semester")),
            status=form.get("status") if form.get("status") in ("Available", "Maintenance") else "Available",
            amenities=form.get("amenities") or None, notes=form.get("notes") or None,
        )
        db.session.add(room)
        db.session.commit()
        log_action("Room created", entity="room", detail=room.room_number)
        flash(f"Room {room.room_number} created.", "success")
        return redirect(url_for("admin.rooms"))

    return render_template("admin/room_form.html", form=form, room_types=ROOM_TYPES, room=None)


@admin_bp.route("/rooms/<int:room_id>/edit", methods=["GET", "POST"])
def room_edit(room_id):
    room = db.session.get(Room, room_id) or abort(404)
    form = {
        "room_number": room.room_number, "block": room.block or "", "floor": room.floor,
        "room_type": room.room_type, "capacity": room.capacity,
        "fee_per_semester": float(room.fee_per_semester or 0), "status": room.status,
        "amenities": room.amenities or "", "notes": room.notes or "",
    }
    if request.method == "POST":
        form = {k: clean(v) for k, v in request.form.items()}
        errors = []
        number = form.get("room_number", "").upper()
        if Room.query.filter(func.lower(Room.room_number) == number.lower(),
                             Room.id != room.id).first():
            errors.append("Another room already uses this number.")
        capacity = to_int(form.get("capacity"), room.capacity)
        if capacity < room.occupied_beds:
            errors.append(
                f"Capacity cannot be below the {room.occupied_beds} beds currently occupied."
            )
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/room_form.html", form=form, room=room,
                                   room_types=ROOM_TYPES), 400
        room.room_number = number
        room.block = form.get("block") or None
        room.floor = to_int(form.get("floor"))
        room.room_type = form.get("room_type") if form.get("room_type") in ROOM_TYPES else room.room_type
        room.capacity = capacity
        room.fee_per_semester = to_float(form.get("fee_per_semester"))
        room.status = form.get("status") if form.get("status") in ("Available", "Maintenance") else room.status
        room.amenities = form.get("amenities") or None
        room.notes = form.get("notes") or None
        db.session.commit()
        log_action("Room updated", entity="room", detail=room.room_number)
        flash("Room details updated.", "success")
        return redirect(url_for("admin.rooms"))

    return render_template("admin/room_form.html", form=form, room=room, room_types=ROOM_TYPES)


@admin_bp.route("/rooms/<int:room_id>/status", methods=["POST"])
def room_status(room_id):
    room = db.session.get(Room, room_id) or abort(404)
    new = request.form.get("status")
    if new not in ("Available", "Maintenance"):
        flash("Invalid room status.", "danger")
        return redirect(url_for("admin.rooms"))
    if new == "Maintenance" and room.occupied_beds:
        flash("Vacate the room before marking it under maintenance.", "danger")
        return redirect(url_for("admin.rooms"))
    room.status = new
    db.session.commit()
    log_action(f"Room marked {new}", entity="room", detail=room.room_number)
    flash(f"Room {room.room_number} marked {new.lower()}.", "success")
    return redirect(url_for("admin.rooms"))


@admin_bp.route("/rooms/<int:room_id>/delete", methods=["POST"])
def room_delete(room_id):
    room = db.session.get(Room, room_id) or abort(404)
    if room.occupied_beds:
        flash("This room still has residents. Vacate it before archiving.", "danger")
        return redirect(url_for("admin.rooms"))
    room.status = "Archived"
    db.session.commit()
    log_action("Room archived", entity="room", detail=room.room_number)
    flash(f"Room {room.room_number} archived. Its history is preserved.", "success")
    return redirect(url_for("admin.rooms"))


# --------------------------------------------------------------------------- #
#  Allocations
# --------------------------------------------------------------------------- #
def _assign(student, room, bed_number=None, note=None):
    """Create an allocation while enforcing capacity and bed uniqueness."""
    if not room or room.status == "Archived":
        return "That room is not available."
    if room.live_status == "Maintenance":
        return "That room is under maintenance."
    if student.active_allocation:
        return f"{student.user.name} already has a room. Vacate it first."
    if len(room.active_allocations) >= room.capacity:
        return f"Room {room.room_number} is full - occupancy can never exceed capacity."
    free = room.free_bed_numbers
    if not free:
        return "No free bed in that room."
    if bed_number and bed_number not in free:
        return f"Bed {bed_number} is already taken in room {room.room_number}."
    bed = bed_number or free[0]
    db.session.add(Allocation(
        student_id=student.id, room_id=room.id, bed_number=bed,
        start_date=parse_date(request.form.get("start_date"), date.today()) or date.today(),
        is_active=True, note=note,
    ))
    notify(student.user_id, "Room allocated",
           f"You have been allocated room {room.room_number}, bed {bed}.", icon="bed-double")
    return None


@admin_bp.route("/allocations")
def allocations():
    q = clean(request.args.get("q"))
    active = Allocation.query.filter_by(is_active=True).join(Student).join(Room)
    if q:
        like = f"%{q}%"
        active = active.join(User, Student.user_id == User.id).filter(or_(
            User.name.ilike(like), Student.enrollment_no.ilike(like), Room.room_number.ilike(like)
        ))
    rows = active.order_by(Room.room_number, Allocation.bed_number).all()
    history, page = _paginate(
        Allocation.query.order_by(Allocation.start_date.desc(), Allocation.id.desc()), 15
    )
    unallocated = [
        s for s in Student.query.filter_by(status="Active").all() if not s.active_allocation
    ]
    return render_template(
        "admin/allocations.html", rows=rows, history=history, page=page, q=q,
        unallocated=unallocated, rooms=_room_choices(),
        total_beds=sum(r.capacity for r in Room.query.filter(Room.status != "Archived")),
        occupied_beds=Allocation.query.filter_by(is_active=True).count(),
    )


@admin_bp.route("/allocations/new", methods=["POST"])
def allocation_new():
    student = db.session.get(Student, to_int(request.form.get("student_id")))
    room = db.session.get(Room, to_int(request.form.get("room_id")))
    if not student or not room:
        flash("Please choose both a student and a room.", "danger")
        return redirect(url_for("admin.allocations"))
    error = _assign(student, room, to_int(request.form.get("bed_number")) or None,
                    clean(request.form.get("note")) or "Allocated by administrator")
    if error:
        db.session.rollback()
        flash(error, "danger")
    else:
        db.session.commit()
        log_action("Room allocated", entity="allocation",
                   detail=f"{student.enrollment_no} -> {room.room_number}")
        flash(f"{student.user.name} allocated to room {room.room_number}.", "success")
    return redirect(request.referrer or url_for("admin.allocations"))


@admin_bp.route("/allocations/<int:alloc_id>/vacate", methods=["POST"])
def allocation_vacate(alloc_id):
    alloc = db.session.get(Allocation, alloc_id) or abort(404)
    if not alloc.is_active:
        flash("This allocation is already closed.", "warning")
        return redirect(url_for("admin.allocations"))
    alloc.is_active = False
    alloc.end_date = parse_date(request.form.get("end_date"), date.today()) or date.today()
    notify(alloc.student.user_id, "Room vacated",
           f"You have been moved out of room {alloc.room.room_number}.", icon="log-out")
    db.session.commit()
    log_action("Room vacated", entity="allocation",
               detail=f"{alloc.student.enrollment_no} <- {alloc.room.room_number}")
    flash(f"Room {alloc.room.room_number} vacated for {alloc.student.user.name}.", "success")
    return redirect(request.referrer or url_for("admin.allocations"))


@admin_bp.route("/allocations/<int:alloc_id>/change", methods=["POST"])
def allocation_change(alloc_id):
    alloc = db.session.get(Allocation, alloc_id) or abort(404)
    new_room = db.session.get(Room, to_int(request.form.get("room_id")))
    if not new_room:
        flash("Choose the new room.", "danger")
        return redirect(request.referrer or url_for("admin.allocations"))
    if new_room.id == alloc.room_id:
        flash("The student is already in that room.", "warning")
        return redirect(request.referrer or url_for("admin.allocations"))
    if len(new_room.active_allocations) >= new_room.capacity:
        flash(f"Room {new_room.room_number} is full.", "danger")
        return redirect(request.referrer or url_for("admin.allocations"))
    old_room = alloc.room.room_number
    alloc.is_active = False
    alloc.end_date = date.today()
    db.session.flush()
    error = _assign(alloc.student, new_room, to_int(request.form.get("bed_number")) or None,
                    f"Transferred from room {old_room}")
    if error:
        db.session.rollback()
        flash(error, "danger")
    else:
        db.session.commit()
        log_action("Room allocation changed", entity="allocation",
                   detail=f"{alloc.student.enrollment_no}: {old_room} -> {new_room.room_number}")
        flash(f"Moved {alloc.student.user.name} from {old_room} to {new_room.room_number}.", "success")
    return redirect(request.referrer or url_for("admin.allocations"))


# --------------------------------------------------------------------------- #
#  Fees
# --------------------------------------------------------------------------- #
@admin_bp.route("/fees")
def fees():
    status = request.args.get("status", "")
    q = clean(request.args.get("q"))
    query = FeeRecord.query.join(Student).join(User, Student.user_id == User.id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), Student.enrollment_no.ilike(like),
                                 FeeRecord.title.ilike(like)))
    rows = query.order_by(FeeRecord.due_date.desc(), FeeRecord.id.desc()).all()
    if status:
        rows = [r for r in rows if r.status == status]

    totals = {
        "billed": round(sum(float(r.amount) for r in rows), 2),
        "paid": round(sum(r.paid_amount for r in rows), 2),
        "due": round(sum(r.balance for r in rows), 2),
        "overdue": sum(1 for r in rows if r.status == "Overdue"),
    }
    return render_template(
        "admin/fees.html", rows=rows, totals=totals, status=status, q=q,
        students=[s for s in Student.query.filter_by(status="Active").all()],
        default_fee=Setting.get("default_fee"), session_name=Setting.get("academic_session"),
        rooms=Room.query.filter(Room.status != "Archived").order_by(Room.room_number).all(),
    )


@admin_bp.route("/fees/new", methods=["POST"])
def fee_new():
    title = clean(request.form.get("title")) or "Hostel Fee"
    amount = to_float(request.form.get("amount"))
    due = parse_date(request.form.get("due_date"), date.today()) or date.today()
    semester = clean(request.form.get("semester")) or Setting.get("academic_session")
    target = request.form.get("target")  # single | all | room | year
    description = clean(request.form.get("description")) or None

    if amount <= 0:
        flash("Fee amount must be greater than zero.", "danger")
        return redirect(url_for("admin.fees"))

    if target == "single":
        students = [db.session.get(Student, to_int(request.form.get("student_id")))]
    elif target == "room":
        room = db.session.get(Room, to_int(request.form.get("room_id")))
        students = [a.student for a in room.active_allocations] if room else []
    elif target == "year":
        students = Student.query.filter_by(status="Active", year=request.form.get("year")).all()
    else:
        students = Student.query.filter_by(status="Active").all()

    students = [s for s in students if s]
    if not students:
        flash("No matching students were found, so no fee was assigned.", "warning")
        return redirect(url_for("admin.fees"))
    for s in students:
        db.session.add(FeeRecord(
            student_id=s.id, title=title[:120], description=description,
            amount=amount, due_date=due, semester=semester, created_by=current_user.id,
        ))
        notify(s.user_id, f"New fee assigned: {title}",
               f"₹{amount:,.0f} is due by {due.strftime('%d %b %Y')}.", icon="receipt",
               link=url_for("student.fees"))
    db.session.commit()
    log_action("Fee assigned", entity="fee", detail=f"{title} -> {len(students)} student(s)")
    flash(f"{title} of ₹{amount:,.0f} assigned to {len(students)} student(s).", "success")
    return redirect(url_for("admin.fees"))


@admin_bp.route("/fees/<int:fee_id>/delete", methods=["POST"])
def fee_delete(fee_id):
    fee = db.session.get(FeeRecord, fee_id) or abort(404)
    if fee.payments:
        flash("Payments are linked to this fee record, so it cannot be deleted.", "danger")
        return redirect(url_for("admin.fees"))
    db.session.delete(fee)
    db.session.commit()
    log_action("Fee record deleted", entity="fee", detail=fee.title)
    flash("Fee record deleted.", "success")
    return redirect(url_for("admin.fees"))


@admin_bp.route("/payments")
def payments():
    q = clean(request.args.get("q"))
    method = request.args.get("method", "")
    start = parse_date(request.args.get("start"))
    end = parse_date(request.args.get("end"))
    query = Payment.query.join(Student).join(User, Student.user_id == User.id)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), Student.enrollment_no.ilike(like),
                                 Payment.receipt_no.ilike(like), Payment.reference.ilike(like)))
    if method in PAYMENT_METHODS:
        query = query.filter(Payment.method == method)
    if start:
        query = query.filter(Payment.paid_on >= start)
    if end:
        query = query.filter(Payment.paid_on <= end)
    rows, page = _paginate(query.order_by(Payment.paid_on.desc(), Payment.id.desc()), 15)
    total = float(query.with_entities(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0)
    by_method = dict(
        db.session.query(Payment.method, func.coalesce(func.sum(Payment.amount), 0))
        .group_by(Payment.method).all()
    )
    return render_template(
        "admin/payments.html", rows=rows, page=page, q=q, method=method,
        start=request.args.get("start", ""), end=request.args.get("end", ""),
        methods=PAYMENT_METHODS, total=total,
        by_method={k: float(v) for k, v in by_method.items()},
        students=[s for s in Student.query.filter_by(status="Active").all()],
    )


@admin_bp.route("/payments/new", methods=["POST"])
def payment_new():
    student = db.session.get(Student, to_int(request.form.get("student_id")))
    amount = to_float(request.form.get("amount"))
    method = request.form.get("method") if request.form.get("method") in PAYMENT_METHODS else "Cash"
    paid_on = parse_date(request.form.get("paid_on"), date.today()) or date.today()
    fee_id = to_int(request.form.get("fee_record_id")) or None
    reference = clean(request.form.get("reference")) or None

    if not student:
        flash("Select the student this payment belongs to.", "danger")
        return redirect(url_for("admin.payments"))
    if amount <= 0:
        flash("Payment amount must be greater than zero.", "danger")
        return redirect(url_for("admin.payments"))
    if fee_id:
        fee = db.session.get(FeeRecord, fee_id)
        if not fee or fee.student_id != student.id:
            flash("That fee record does not belong to the selected student.", "danger")
            return redirect(url_for("admin.payments"))
    payment = Payment(
        receipt_no=next_receipt_no(), student_id=student.id, fee_record_id=fee_id,
        amount=amount, paid_on=paid_on, method=method, reference=reference,
        note=clean(request.form.get("note")) or None, recorded_by=current_user.id,
    )
    db.session.add(payment)
    notify(student.user_id, "Payment recorded",
           f"₹{amount:,.0f} received via {method}. Receipt {payment.receipt_no}.",
           icon="badge-check", link=url_for("student.payments"))
    db.session.commit()
    log_action("Payment recorded", entity="payment",
               detail=f"{payment.receipt_no} ₹{amount:,.0f} ({method})")
    flash(f"Payment {payment.receipt_no} recorded for {student.user.name}.", "success")
    return redirect(request.referrer or url_for("admin.payments"))


@admin_bp.route("/payments/<int:payment_id>/delete", methods=["POST"])
def payment_delete(payment_id):
    payment = db.session.get(Payment, payment_id) or abort(404)
    receipt = payment.receipt_no
    db.session.delete(payment)
    db.session.commit()
    log_action("Payment entry deleted", entity="payment", detail=receipt)
    flash(f"Payment {receipt} removed from the records.", "success")
    return redirect(request.referrer or url_for("admin.payments"))


@admin_bp.route("/payments/<int:payment_id>/receipt")
def payment_receipt(payment_id):
    payment = db.session.get(Payment, payment_id) or abort(404)
    return render_template("admin/receipt.html", payment=payment, student=payment.student)


# --------------------------------------------------------------------------- #
#  Complaints
# --------------------------------------------------------------------------- #
@admin_bp.route("/complaints")
def complaints():
    status = request.args.get("status", "")
    category = request.args.get("category", "")
    q = clean(request.args.get("q"))
    query = Complaint.query.join(Student).join(User, Student.user_id == User.id)
    if status in COMPLAINT_STATUSES:
        query = query.filter(Complaint.status == status)
    if category in COMPLAINT_CATEGORIES:
        query = query.filter(Complaint.category == category)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Complaint.subject.ilike(like), Complaint.ticket_no.ilike(like),
                                 User.name.ilike(like), Student.enrollment_no.ilike(like)))
    rows, page = _paginate(query.order_by(Complaint.created_at.desc()), 12)
    stats = {s: Complaint.query.filter_by(status=s).count() for s in COMPLAINT_STATUSES}
    by_category = dict(
        db.session.query(Complaint.category, func.count(Complaint.id))
        .group_by(Complaint.category).all()
    )
    unread_messages = ContactMessage.query.filter_by(is_read=False).count()
    return render_template(
        "admin/complaints.html", rows=rows, page=page, status=status,
        category=category, q=q, stats=stats, categories=COMPLAINT_CATEGORIES,
        statuses=COMPLAINT_STATUSES,
        cat_labels=list(by_category.keys()), cat_values=list(by_category.values()),
        unread_messages=unread_messages,
    )


@admin_bp.route("/complaints/<int:complaint_id>", methods=["GET", "POST"])
def complaint_detail(complaint_id):
    complaint = db.session.get(Complaint, complaint_id) or abort(404)

    if request.method == "POST":
        action = request.form.get("action", "respond")
        new_status = request.form.get("status")
        message = clean(request.form.get("message"))

        if action == "status" or new_status:
            if new_status in COMPLAINT_STATUSES:
                complaint.status = new_status
                complaint.handled_by = current_user.id
                complaint.updated_at = datetime.utcnow()
                if new_status == "Resolved":
                    complaint.resolved_at = datetime.utcnow()
                elif new_status != "Resolved":
                    complaint.resolved_at = None
                notify(complaint.student.user_id,
                       f"Complaint {complaint.ticket_no} is now {new_status}",
                       message or f"Status updated by the hostel office.",
                       icon="clipboard-check",
                       link=url_for("student.complaint_detail", complaint_id=complaint.id))

        if message:
            db.session.add(ComplaintResponse(
                complaint_id=complaint.id, author_id=current_user.id, message=message[:2000]
            ))
            complaint.updated_at = datetime.utcnow()
            if action == "respond":
                notify(complaint.student.user_id,
                       f"New response on {complaint.ticket_no}", message[:120],
                       icon="message-square",
                       link=url_for("student.complaint_detail", complaint_id=complaint.id))

        db.session.commit()
        log_action("Complaint updated", entity="complaint",
                   detail=f"{complaint.ticket_no} -> {complaint.status}")
        flash("Complaint updated and the student was notified in-app.", "success")
        return redirect(url_for("admin.complaint_detail", complaint_id=complaint.id))

    return render_template("admin/complaint_detail.html", complaint=complaint,
                           statuses=COMPLAINT_STATUSES)


@admin_bp.route("/messages")
def messages():
    rows = ContactMessage.query.filter_by(source="public").order_by(
        ContactMessage.created_at.desc()).all()
    student_rows = ContactMessage.query.filter_by(source="student").order_by(
        ContactMessage.created_at.desc()).all()
    return render_template("admin/messages.html", rows=rows, student_rows=student_rows)


@admin_bp.route("/messages/<int:msg_id>/read", methods=["POST"])
def message_read(msg_id):
    msg = db.session.get(ContactMessage, msg_id) or abort(404)
    msg.is_read = not msg.is_read
    db.session.commit()
    return redirect(request.referrer or url_for("admin.messages"))


# --------------------------------------------------------------------------- #
#  Announcements
# --------------------------------------------------------------------------- #
@admin_bp.route("/announcements", methods=["GET", "POST"])
def announcements():
    if request.method == "POST":
        title = clean(request.form.get("title"))
        body = clean(request.form.get("body"))
        tag = request.form.get("tag") if request.form.get("tag") in ANNOUNCEMENT_TAGS else "General"
        if len(title) < 5 or len(body) < 10:
            flash("Give the announcement a title and at least a short message.", "danger")
            return redirect(url_for("admin.announcements"))
        ann = Announcement(
            title=title[:150], body=body[:4000], tag=tag,
            is_published=request.form.get("is_published") == "1",
            is_pinned=request.form.get("is_pinned") == "1", posted_by=current_user.id,
        )
        db.session.add(ann)
        db.session.flush()
        for s in Student.query.filter_by(status="Active").all():
            notify(s.user_id, f"New announcement: {ann.title}", body[:120], icon="megaphone",
                   link=url_for("student.announcements"))
        db.session.commit()
        log_action("Announcement published", entity="announcement", detail=ann.title)
        flash("Announcement saved and students notified in-app.", "success")
        return redirect(url_for("admin.announcements"))

    rows = Announcement.query.order_by(
        Announcement.is_pinned.desc(), Announcement.created_at.desc()).all()
    return render_template("admin/announcements.html", rows=rows, tags=ANNOUNCEMENT_TAGS)


@admin_bp.route("/announcements/<int:ann_id>/edit", methods=["POST"])
def announcement_edit(ann_id):
    ann = db.session.get(Announcement, ann_id) or abort(404)
    ann.title = clean(request.form.get("title"))[:150] or ann.title
    ann.body = clean(request.form.get("body"))[:4000] or ann.body
    if request.form.get("tag") in ANNOUNCEMENT_TAGS:
        ann.tag = request.form["tag"]
    ann.is_published = request.form.get("is_published") == "1"
    ann.is_pinned = request.form.get("is_pinned") == "1"
    db.session.commit()
    log_action("Announcement updated", entity="announcement", detail=ann.title)
    flash("Announcement updated.", "success")
    return redirect(url_for("admin.announcements"))


@admin_bp.route("/announcements/<int:ann_id>/toggle", methods=["POST"])
def announcement_toggle(ann_id):
    ann = db.session.get(Announcement, ann_id) or abort(404)
    ann.is_published = not ann.is_published
    db.session.commit()
    flash(f"Announcement {'published' if ann.is_published else 'unpublished'}.", "success")
    return redirect(url_for("admin.announcements"))


@admin_bp.route("/announcements/<int:ann_id>/delete", methods=["POST"])
def announcement_delete(ann_id):
    ann = db.session.get(Announcement, ann_id) or abort(404)
    db.session.delete(ann)
    db.session.commit()
    log_action("Announcement deleted", entity="announcement", detail=ann.title)
    flash("Announcement deleted.", "success")
    return redirect(url_for("admin.announcements"))


# --------------------------------------------------------------------------- #
#  Staff
# --------------------------------------------------------------------------- #
@admin_bp.route("/staff", methods=["GET", "POST"])
def staff():
    if request.method == "POST":
        staff_id = to_int(request.form.get("staff_id"))
        name = clean(request.form.get("full_name"))
        role = request.form.get("role")
        phone = clean(request.form.get("phone"))
        email = clean(request.form.get("email")).lower()
        errors = []
        if len(name) < 3:
            errors.append("Staff name is required.")
        if role not in STAFF_ROLES:
            errors.append("Choose a valid staff role.")
        if phone and not valid_phone(phone):
            errors.append("Enter a valid phone number.")
        if email and not valid_email(email):
            errors.append("Enter a valid email address or leave it blank.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("admin.staff"))

        if staff_id:
            member = db.session.get(Staff, staff_id) or abort(404)
            message = "Staff record updated."
        else:
            member = Staff()
            db.session.add(member)
            message = "Staff member added."
        member.full_name = name
        member.role = role
        member.phone = phone or None
        member.email = email or None
        member.shift = clean(request.form.get("shift")) or None
        member.joined_on = parse_date(request.form.get("joined_on"), date.today())
        member.status = request.form.get("status") if request.form.get("status") in (
            "Active", "On Leave", "Inactive") else "Active"
        member.notes = clean(request.form.get("notes")) or None
        db.session.commit()
        log_action("Staff saved", entity="staff", detail=name)
        flash(message, "success")
        return redirect(url_for("admin.staff"))

    q = clean(request.args.get("q"))
    role = request.args.get("role", "")
    query = Staff.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Staff.full_name.ilike(like),
                                 Staff.phone.ilike(like), Staff.email.ilike(like)))
    if role in STAFF_ROLES:
        query = query.filter(Staff.role == role)
    rows = query.order_by(Staff.role, Staff.full_name).all()
    return render_template("admin/staff.html", rows=rows, roles=STAFF_ROLES, q=q, role=role,
                           counts=Counter(s.role for s in Staff.query.all()))


@admin_bp.route("/staff/<int:staff_id>/toggle", methods=["POST"])
def staff_toggle(staff_id):
    member = db.session.get(Staff, staff_id) or abort(404)
    member.status = "Inactive" if member.status == "Active" else "Active"
    db.session.commit()
    flash(f"{member.full_name} is now {member.status.lower()}.", "success")
    return redirect(url_for("admin.staff"))


@admin_bp.route("/staff/<int:staff_id>/delete", methods=["POST"])
def staff_delete(staff_id):
    member = db.session.get(Staff, staff_id) or abort(404)
    name = member.full_name
    db.session.delete(member)
    db.session.commit()
    log_action("Staff removed", entity="staff", detail=name)
    flash(f"{name} removed from the staff list.", "success")
    return redirect(url_for("admin.staff"))


# --------------------------------------------------------------------------- #
#  Reports, quality (TQM), settings
# --------------------------------------------------------------------------- #
@admin_bp.route("/reports")
def reports():
    stats = _core_stats()
    labels, collected, billed = _month_series(6)

    type_rows = []
    rooms = Room.query.filter(Room.status != "Archived").all()
    for rtype in ROOM_TYPES:
        group = [r for r in rooms if r.room_type == rtype]
        if not group:
            continue
        type_rows.append({
            "type": rtype,
            "rooms": len(group),
            "capacity": sum(r.capacity for r in group),
            "occupied": sum(r.occupied_beds for r in group),
            "free": sum(r.free_beds for r in group),
            "revenue_billed": sum(float(r.fee_per_semester or 0) * r.occupied_beds for r in group),
        })

    by_method = [
        (m, float(v)) for m, v in db.session.query(
            Payment.method, func.coalesce(func.sum(Payment.amount), 0)
        ).group_by(Payment.method).all()
    ]
    dues = sorted(
        [s for s in Student.query.filter_by(status="Active").all() if s.balance > 0],
        key=lambda s: s.balance, reverse=True,
    )[:10]
    complaints_by_cat = dict(
        db.session.query(Complaint.category, func.count(Complaint.id))
        .group_by(Complaint.category).all()
    )
    status_counts = {s: Complaint.query.filter_by(status=s).count() for s in COMPLAINT_STATUSES}
    resolved = Complaint.query.filter(Complaint.resolved_at.isnot(None)).all()
    avg_hours = round(sum(c.resolution_hours for c in resolved) / len(resolved), 1) if resolved else 0

    return render_template(
        "admin/reports.html", stats=stats, type_rows=type_rows, month_labels=labels,
        month_collected=collected, month_billed=billed, by_method=by_method, dues=dues,
        method_labels=[m for m, _ in by_method], method_values=[v for _, v in by_method],
        cat_labels=list(complaints_by_cat.keys()), cat_values=list(complaints_by_cat.values()),
        status_counts=status_counts, avg_hours=avg_hours,
        payment_count=Payment.query.count(), fee_count=FeeRecord.query.count(),
    )


@admin_bp.route("/quality", methods=["GET", "POST"])
def quality():
    """SQC / TQM screen: Pareto of complaints + defect (FMEA) log + PDCA tracker."""
    if request.method == "POST":
        kind = request.form.get("kind")
        if kind == "defect":
            defect = DefectLog(
                module=clean(request.form.get("module"))[:60] or "General",
                description=clean(request.form.get("description"))[:255],
                category=request.form.get("category") or "Software Code",
                severity=min(max(to_int(request.form.get("severity"), 3), 1), 10),
                occurrence=min(max(to_int(request.form.get("occurrence"), 3), 1), 10),
                detection=min(max(to_int(request.form.get("detection"), 3), 1), 10),
                status=request.form.get("status") or "Open",
                logged_on=parse_date(request.form.get("logged_on"), date.today()),
            )
            if not defect.description:
                flash("Describe the defect before saving.", "danger")
                return redirect(url_for("admin.quality"))
            db.session.add(defect)
            db.session.commit()
            flash("Defect logged with an RPN score.", "success")
        elif kind == "pdca":
            entry = PDCALog(
                phase=request.form.get("phase") if request.form.get("phase") in (
                    "Plan", "Do", "Check", "Act") else "Plan",
                title=clean(request.form.get("title"))[:150] or "Improvement action",
                detail=clean(request.form.get("detail"))[:2000],
                owner=clean(request.form.get("owner"))[:120] or current_user.name,
            )
            db.session.add(entry)
            db.session.commit()
            flash("PDCA entry recorded.", "success")
        return redirect(url_for("admin.quality"))

    # Pareto data: complaint categories sorted descending (real complaint counts)
    raw = dict(
        db.session.query(Complaint.category, func.count(Complaint.id))
        .group_by(Complaint.category).all()
    )
    ordered = sorted(raw.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(v for _, v in ordered) or 0
    pareto, running = [], 0
    for cat, count in ordered:
        running += count
        pareto.append({
            "category": cat, "count": count, "cum_count": running,
            "pct": round(count * 100 / total, 1) if total else 0,
            "cum_pct": round(running * 100 / total, 1) if total else 0,
        })
    vital = [p for p in pareto if p["cum_pct"] <= 80]

    defects = DefectLog.query.order_by(DefectLog.id.desc()).all()
    fmea = sorted(defects, key=lambda d: d.rpn, reverse=True)
    pdca = PDCALog.query.order_by(PDCALog.created_at.desc()).all()
    resolved = Complaint.query.filter(Complaint.resolved_at.isnot(None)).all()
    ctq = {
        "total": total,
        "resolved": len(resolved),
        "rate": round(len(resolved) * 100 / total, 1) if total else 0,
        "avg_hours": round(sum(c.resolution_hours for c in resolved) / len(resolved), 1) if resolved else 0,
        "sla": sum(1 for c in resolved if (c.resolution_hours or 99) <= 48),
        "open_defects": sum(1 for d in defects if d.status != "Closed"),
        "max_rpn": max([d.rpn for d in defects], default=0),
    }
    return render_template(
        "admin/quality.html", pareto=pareto, vital=vital, fmea=fmea, pdca=pdca, ctq=ctq,
        categories=COMPLAINT_CATEGORIES,
        pareto_total=total, pareto_threshold=round(total * 0.8, 2),
    )


@admin_bp.route("/quality/defect/<int:defect_id>/close", methods=["POST"])
def defect_close(defect_id):
    defect = db.session.get(DefectLog, defect_id) or abort(404)
    defect.status = "Closed" if defect.status != "Closed" else "Open"
    db.session.commit()
    flash(f"Defect marked {defect.status.lower()}.", "success")
    return redirect(url_for("admin.quality"))


@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    keys = list(Setting.DEFAULT.keys())
    if request.method == "POST":
        form_kind = request.form.get("form_kind", "general")
        if form_kind == "password":
            current = request.form.get("current_password") or ""
            new = request.form.get("new_password") or ""
            confirm = request.form.get("confirm_password") or ""
            if not current_user.check_password(current):
                flash("Current password is incorrect.", "danger")
            elif new != confirm:
                flash("New passwords do not match.", "danger")
            elif password_problem(new):
                flash(password_problem(new), "danger")
            else:
                current_user.set_password(new)
                db.session.commit()
                log_action("Administrator changed password", entity="auth")
                flash("Administrator password updated.", "success")
            return redirect(url_for("admin.settings"))

        for key in keys:
            if key in request.form:
                Setting.set(key, clean(request.form.get(key)))
        Setting.set("registration_open", "1" if request.form.get("registration_open") == "1" else "0")
        db.session.commit()
        log_action("Settings updated", entity="settings")
        flash("Hostel settings saved.", "success")
        return redirect(url_for("admin.settings"))

    admins = User.query.filter_by(role="admin").all()
    return render_template(
        "admin/settings.html",
        values={k: Setting.get(k) for k in keys},
        registration_open=Setting.get_bool("registration_open", True),
        admins=admins,
        db_uri=__import__("flask").current_app.config["SQLALCHEMY_DATABASE_URI"].split("///")[-1],
    )


@admin_bp.route("/settings/admin", methods=["POST"])
def settings_add_admin():
    name = clean(request.form.get("name"))
    email = clean(request.form.get("email")).lower()
    password = request.form.get("password") or ""
    if len(name) < 3 or not valid_email(email):
        flash("Provide a valid administrator name and email.", "danger")
        return redirect(url_for("admin.settings"))
    if User.query.filter(func.lower(User.email) == email).first():
        flash("An account with that email already exists.", "danger")
        return redirect(url_for("admin.settings"))
    problem = password_problem(password)
    if problem:
        flash(problem, "danger")
        return redirect(url_for("admin.settings"))
    admin = User(name=name, email=email, role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    log_action("Administrator account created", entity="auth", detail=email)
    flash(f"Administrator {name} created.", "success")
    return redirect(url_for("admin.settings"))


# --------------------------------------------------------------------------- #
#  CSV exports
# --------------------------------------------------------------------------- #
@admin_bp.route("/export/<kind>.csv")
def export_csv(kind):
    if kind == "students":
        rows = [
            [s.enrollment_no, s.user.name, s.user.email, s.user.phone or "", s.course or "",
             s.department or "", s.year or "", s.status,
             s.room.room_number if s.room else "Unallocated", s.balance]
            for s in Student.query.join(User).order_by(User.name).all()
        ]
        return CSVResponse.build(
            "students.csv",
            ["Enrollment No", "Name", "Email", "Phone", "Course", "Department", "Year",
             "Status", "Room", "Balance Due"],
            rows,
        )
    if kind == "payments":
        rows = [
            [p.receipt_no, p.paid_on.isoformat(), p.student.enrollment_no, p.student.user.name,
             float(p.amount), p.method, p.reference or "",
             (p.fee_record.title if p.fee_record else "General"),
             p.recorder.name if p.recorder else ""]
            for p in Payment.query.order_by(Payment.paid_on.desc()).all()
        ]
        return CSVResponse.build(
            "payments.csv",
            ["Receipt No", "Paid On", "Enrollment No", "Student", "Amount", "Method",
             "Reference", "Fee Head", "Recorded By"],
            rows,
        )
    if kind == "dues":
        rows = []
        for f in FeeRecord.query.order_by(FeeRecord.due_date).all():
            if f.balance > 0:
                rows.append([
                    f.student.enrollment_no, f.student.user.name,
                    f.student.room.room_number if f.student.room else "Unallocated",
                    f.title, float(f.amount), f.paid_amount, f.balance,
                    f.due_date.isoformat(), f.status,
                ])
        return CSVResponse.build(
            "pending-dues.csv",
            ["Enrollment No", "Student", "Room", "Fee Head", "Amount", "Paid", "Balance",
             "Due Date", "Status"],
            rows,
        )
    if kind == "rooms":
        rows = [
            [r.room_number, r.block or "", r.floor, r.room_type, r.capacity, r.occupied_beds,
             r.free_beds, float(r.fee_per_semester or 0), r.live_status]
            for r in Room.query.filter(Room.status != "Archived").order_by(Room.room_number).all()
        ]
        return CSVResponse.build(
            "rooms.csv",
            ["Room", "Block", "Floor", "Type", "Capacity", "Occupied", "Free",
             "Fee / Semester", "Status"],
            rows,
        )
    if kind == "complaints":
        rows = [
            [c.ticket_no, c.created_at.strftime("%Y-%m-%d"), c.student.enrollment_no,
             c.student.user.name, c.category, c.subject, c.status, c.priority,
             c.resolution_hours if c.resolution_hours is not None else ""]
            for c in Complaint.query.order_by(Complaint.created_at.desc()).all()
        ]
        return CSVResponse.build(
            "complaints.csv",
            ["Ticket", "Logged On", "Enrollment No", "Student", "Category", "Subject",
             "Status", "Priority", "Resolution Hours"],
            rows,
        )
    if kind == "allocations":
        rows = [
            [a.student.enrollment_no, a.student.user.name, a.room.room_number,
             a.room.room_type, a.bed_number, a.start_date.isoformat() if a.start_date else "",
             a.end_date.isoformat() if a.end_date else "",
             "Active" if a.is_active else "Closed"]
            for a in Allocation.query.order_by(Allocation.start_date.desc()).all()
        ]
        return CSVResponse.build(
            "allocations.csv",
            ["Enrollment No", "Student", "Room", "Room Type", "Bed", "From", "To", "Status"],
            rows,
        )
    abort(404)
