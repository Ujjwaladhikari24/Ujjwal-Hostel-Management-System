"""Optional DEMO DATA loader — for review / viva demonstrations only.

    flask --app app.py seed-demo --yes

Nothing here runs automatically. Every figure shown in the dashboards is
computed from these rows, so once seeded the app reports "real" numbers —
delete instance/hostel.db if you want an empty, production-like database.
"""
from datetime import date, datetime, timedelta

from hms.extensions import db
from hms.models import (Allocation, Announcement, Complaint, ComplaintResponse,
                        DefectLog, FeeRecord, Notification, PDCALog, Payment,
                        Room, Setting, Staff, Student, User)

DEMO_STUDENT_PASSWORD = "Student@123"

ROOMS = [
    # (number, block, floor, type, capacity, fee)
    ("A-101", "Block A", 1, "Single Sharing", 1, 72000),
    ("A-102", "Block A", 1, "Double Sharing", 2, 48000),
    ("A-103", "Block A", 1, "Double Sharing", 2, 48000),
    ("A-104", "Block A", 1, "Triple Sharing", 3, 36000),
    ("A-201", "Block A", 2, "Single Sharing", 1, 72000),
    ("A-202", "Block A", 2, "Double Sharing", 2, 48000),
    ("A-203", "Block A", 2, "Four Sharing", 4, 30000),
    ("A-204", "Block A", 2, "Triple Sharing", 3, 36000),
    ("B-101", "Block B", 1, "Double Sharing", 2, 46000),
    ("B-102", "Block B", 1, "Double Sharing", 2, 46000),
    ("B-103", "Block B", 1, "Four Sharing", 4, 28000),
    ("B-201", "Block B", 2, "Single Sharing", 1, 68000),
    ("B-202", "Block B", 2, "Triple Sharing", 3, 34000),
    ("B-203", "Block B", 2, "Double Sharing", 2, 46000),
    ("B-204", "Block B", 2, "Double Sharing", 2, 46000),
    ("B-205", "Block B", 2, "Four Sharing", 4, 28000),
]

STUDENTS = [
    # (name, enrollment, course, dept, year, phone)
    ("Aarav Sharma", "23CS1001", "B.Tech", "Computer Science", "2nd Year", "9812345601"),
    ("Diya Patel", "23CS1002", "B.Tech", "Computer Science", "2nd Year", "9812345602"),
    ("Kabir Verma", "23EC1015", "B.Tech", "Electronics", "2nd Year", "9812345603"),
    ("Ananya Nair", "22ME1042", "B.Tech", "Mechanical", "3rd Year", "9812345604"),
    ("Rohan Mehta", "22CS1088", "B.Tech", "Computer Science", "3rd Year", "9812345605"),
    ("Ishita Rao", "24BA2007", "BBA", "Management", "1st Year", "9812345606"),
    ("Vivaan Joshi", "24BA2011", "BBA", "Management", "1st Year", "9812345607"),
    ("Meera Iyer", "23EE1009", "B.Tech", "Electrical", "2nd Year", "9812345608"),
    ("Arjun Singh", "21CE3004", "B.Tech", "Civil", "4th Year", "9812345609"),
    ("Saanvi Gupta", "22BT1050", "B.Sc", "Biotechnology", "3rd Year", "9812345610"),
    ("Aditya Kulkarni", "24CS2101", "B.Tech", "Computer Science", "1st Year", "9812345611"),
    ("Nisha Bhatt", "23MB2015", "MBA", "Finance", "Postgraduate", "9812345612"),
    ("Yash Chauhan", "22AR1008", "B.Arch", "Architecture", "3rd Year", "9812345613"),
    ("Tara Menon", "24MC2022", "MCA", "Computer Applications", "Postgraduate", "9812345614"),
    ("Devansh Yadav", "21CS1066", "B.Tech", "Computer Science", "4th Year", "9812345615"),
    ("Priya Soni", "23CH1033", "B.Tech", "Chemical", "2nd Year", "9812345616"),
    ("Neel Kapoor", "24EE2050", "B.Tech", "Electrical", "1st Year", "9812345617"),
    ("Riya Saxena", "22BT1077", "B.Sc", "Biotechnology", "3rd Year", "9812345618"),
]

STAFF = [
    ("Ramesh Iyer", "Warden", "Morning", "9800000001", "ramesh.iyer@ujjwalhostel.edu.in", "Overall hostel administration"),
    ("Sunita Deshmukh", "Assistant Warden", "Evening", "9800000002", "sunita.d@ujjwalhostel.edu.in", "Block A supervision"),
    ("Mahesh Prasad", "Security Staff", "Night", "9800000003", "", "Main gate & visitor log"),
    ("Lakshmi Devi", "Cleaning Staff", "Morning", "9800000004", "", "Floors 1–2, Block A"),
    ("Imran Khan", "Maintenance Staff", "Rotational", "9800000005", "", "Electrical & plumbing"),
    ("Shalini Verma", "Mess Manager", "Morning", "9800000006", "mess@ujjwalhostel.edu.in", "Menu planning & hygiene"),
    ("Gopal Reddy", "Security Staff", "Day", "9800000007", "", "Block B gate"),
]

ANNOUNCEMENTS = [
    ("Semester hostel fee due on 15 Dec", "The semester hostel fee for the 2026–27 session is due on 15 December. Pay at the accounts counter (cash/UPI/bank transfer) — receipts appear instantly in your portal.", "Fees", True),
    ("Water tank cleaning on Saturday", "Block A and B overhead tanks will be cleaned this Saturday between 10 AM and 2 PM. Water supply will be intermittent during this window.", "Maintenance", False),
    ("Revised mess menu from Monday", "A revised weekly mess menu takes effect from Monday, including a South Indian breakfast on Wednesdays and a Sunday special lunch.", "Mess", False),
    ("Diwali vacation — hostel closing dates", "The hostel will remain open through the vacation. Residents staying back must inform the warden's office and sign the vacation register.", "Holiday", False),
    ("Inter-hostel sports meet registrations", "Register your team for the inter-hostel cricket and badminton tournament at the warden's office before Friday evening.", "Event", False),
]

COMPLAINTS = [
    ("Electricity", "Frequent power cuts in room A-202", "The power in A-202 trips almost every evening between 8 and 10 PM. The MCB switches off and we have to reset it manually.", "Resolved", "High"),
    ("Wi-Fi", "Slow internet in Block B corridors", "Wi-Fi speed drops below 1 Mbps near B-203 in the evening. Video lectures keep buffering.", "In Progress", "Normal"),
    ("Water Supply", "No hot water in the morning", "The geyser on the second floor of Block A has not been working for three days. Hot water is unavailable before 8 AM.", "Pending", "High"),
    ("Cleaning", "Corridor not cleaned for two days", "The second floor corridor of Block A has not been swept since Monday and the bins are overflowing.", "Resolved", "Normal"),
    ("Food Quality", "Undercooked rice at dinner", "The rice served at Tuesday dinner was undercooked and some students had to skip the meal.", "In Progress", "Normal"),
    ("Room Maintenance", "Window latch broken in B-102", "The window latch in B-102 is broken since last week. It cannot be locked at night.", "Pending", "High"),
    ("Room Maintenance", "Request for an extra study table", "Two of us in A-103 share a single study table. Could we get one more before the exams?", "Rejected", "Low"),
    ("Security", "Main gate left unattended at night", "On Friday after 11 PM the main gate was open and the security desk was empty for around 20 minutes.", "Resolved", "High"),
    ("Electricity", "Tube light flickering in study hall", "The second tube light in the study hall flickers continuously, making it hard to read at night.", "Resolved", "Low"),
    ("Wi-Fi", "Cannot connect to hostel Wi-Fi after password reset", "After resetting my portal password, my devices no longer connect to the hostel network. Please re-register the MAC address.", "Pending", "Normal"),
    ("Water Supply", "Leaking tap in washroom B-204", "The tap in the common washroom of B-204 keeps dripping and wastes water all day.", "In Progress", "Normal"),
    ("Cleaning", "Pest control needed in Block B mess area", "There are cockroaches near the mess storage area. A pest control round would help.", "Resolved", "Normal"),
    ("Food Quality", "Breakfast variety is limited", "The same poha and bread is served daily. Requesting some variety in the breakfast menu.", "Pending", "Low"),
    ("Security", "CCTV camera at B gate not working", "The camera at the Block B gate appears to be switched off since last week.", "Pending", "Normal"),
]

RESPONSES = {
    "Resolved": "Thanks for reporting. The maintenance team attended to this and the issue has been closed. Please reopen the ticket if it recurs.",
    "In Progress": "We have assigned this to the maintenance team and they are working on it. Expected to be closed within two working days.",
    "Pending": "Your complaint has been received and is queued with the maintenance team. We will update you here shortly.",
    "Rejected": "This request falls outside current hostel policy as each resident is provided one study table. Please contact the warden's office to discuss alternatives.",
}

DEFECTS = [
    ("Room allocation", "Two students could be assigned the same bed when submitted simultaneously", "Software Code", 8, 3, 4, "Closed"),
    ("Fee records", "Balance not recalculated after a payment entry was deleted", "Software Code", 7, 2, 3, "Closed"),
    ("Complaint workflow", "Status change did not notify the student in-app", "Process", 5, 3, 2, "Closed"),
    ("Student registration", "Duplicate enrollment numbers accepted before validation was tightened", "Software Code", 7, 2, 2, "Closed"),
    ("Room management", "Capacity could be edited below current occupancy", "Software Code", 6, 2, 3, "Open"),
    ("Reports", "CSV export showed ₹ symbol incorrectly in older spreadsheet versions", "Software Code", 3, 2, 2, "Closed"),
    ("Authentication", "Session expired while a long form was open, losing input", "People", 4, 4, 3, "Open"),
]

PDCA = [
    ("Plan", "Eliminate over-allocation by enforcing capacity at the allocation service layer", "Identified from FMEA: allocation race condition. Plan: validate capacity + bed uniqueness inside the same transaction."),
    ("Do", "Added server-side capacity and bed-uniqueness checks plus a single-active-allocation rule", "All allocation paths (admin form, transfer, bulk) now go through one validated helper."),
    ("Check", "Audited 30 days of allocation records for overlaps and over-capacity rooms", "Zero overlaps and zero rooms above capacity since the change."),
    ("Act", "Standardised the check and documented it in the allocation module", "Validation is now a shared helper, so any future allocation path inherits the same guard."),
    ("Plan", "Reduce complaint resolution time below 48 hours", "Add a due-time indicator and status workflow with notifications."),
]


def _reset():
    for model in (Payment, FeeRecord, ComplaintResponse, Complaint, Allocation, DefectLog,
                  PDCALog, Announcement, Notification, Student, Room, Staff):
        db.session.query(model).delete()
    db.session.query(User).filter(User.role == "student").delete()
    db.session.commit()


def seed():
    db.create_all()
    _reset()

    for key, value in Setting.DEFAULT.items():
        if db.session.get(Setting, key) is None:
            db.session.add(Setting(key=key, value=value))

    # ---- rooms ---------------------------------------------------------
    rooms = []
    for number, block, floor, rtype, capacity, fee in ROOMS:
        room = Room(
            room_number=number, block=block, floor=floor, room_type=rtype,
            capacity=capacity, fee_per_semester=fee, status="Available",
            amenities="Study table, wardrobe, fan, Wi-Fi" + (", attached bath" if capacity <= 2 else ""),
        )
        db.session.add(room)
        rooms.append(room)
    db.session.flush()
    rooms[14].status = "Maintenance"
    rooms[14].notes = "Bathroom re-tiling in progress until next week."

    # ---- students ------------------------------------------------------
    students = []
    today = date.today()
    for i, (name, enroll, course, dept, year, phone) in enumerate(STUDENTS):
        user = User(
            name=name, email=f"{enroll.lower()}@student.ujjwalhostel.edu.in",
            phone=f"+91 {phone}", role="student",
            created_at=datetime.utcnow() - timedelta(days=200 - i * 3),
        )
        user.set_password(DEMO_STUDENT_PASSWORD)
        db.session.add(user)
        db.session.flush()
        student = Student(
            user_id=user.id, enrollment_no=enroll, course=course, department=dept,
            year=year, guardian_name=f"{name.split()[1]} Family",
            guardian_phone=f"+91 98{phone[-8:]}",
            address="Jaipur, Rajasthan",
        )
        db.session.add(student)
        students.append(student)
    db.session.flush()

    # ---- allocations (respect capacity, leave a few free beds) ---------
    allocatable = [r for r in rooms if r.live_status != "Maintenance"]
    si = 0
    # keep the last two students without a room so the allocation screen has work to do
    max_alloc = len(students) - 2
    for room in allocatable:
        for bed in range(1, room.capacity + 1):
            if si >= max_alloc:
                break
            # leave the last rooms partly empty to show available/partial states
            if room.room_number in ("B-205", "B-204", "A-203") and bed > 1:
                continue
            if room.room_number == "B-201":
                continue
            db.session.add(Allocation(
                student_id=students[si].id, room_id=room.id, bed_number=bed,
                start_date=today - timedelta(days=180 - si * 2), is_active=True,
                note="Initial allocation",
            ))
            si += 1
        if si >= max_alloc:
            break
    db.session.flush()

    # ---- fees ----------------------------------------------------------
    for student in students:
        room = student.room
        amount = float(room.fee_per_semester) if room else 48000.0
        db.session.add(FeeRecord(
            student_id=student.id, title="Semester Hostel Fee",
            description="Includes accommodation and mess charges",
            amount=amount, due_date=today + timedelta(days=20), semester="2026–27",
        ))
        db.session.add(FeeRecord(
            student_id=student.id, title="Mess Advance",
            description="Monthly mess advance",
            amount=6000, due_date=today - timedelta(days=12), semester="2026–27",
        ))
        db.session.add(FeeRecord(
            student_id=student.id, title="Security Deposit (refundable)",
            description="One-time caution deposit",
            amount=5000, due_date=today - timedelta(days=150), semester="2026–27",
        ))
    db.session.flush()

    # ---- payments (admin-recorded) -------------------------------------
    receipts = 1
    methods = ["UPI", "Bank Transfer", "Cash"]
    for i, student in enumerate(students):
        fees = student.fee_records.order_by(FeeRecord.id).all()
        deposit, mess, hostel = fees[2], fees[1], fees[0]
        # everyone paid the refundable deposit
        db.session.add(Payment(
            receipt_no=f"RCPT-{today.year}-{receipts:05d}", student_id=student.id,
            fee_record_id=deposit.id, amount=5000,
            paid_on=today - timedelta(days=145), method="Cash",
            reference="Counter receipt", note="Caution deposit",
        ))
        receipts += 1
        # mess advance: most paid, some pending
        if i % 5 != 0:
            db.session.add(Payment(
                receipt_no=f"RCPT-{today.year}-{receipts:05d}", student_id=student.id,
                fee_record_id=mess.id, amount=6000,
                paid_on=today - timedelta(days=14 + (i % 6)),
                method=methods[i % 3],
                reference=f"UPI{9000000 + i}",
            ))
            receipts += 1
        # hostel fee: partial for many, full for a few
        if i % 4 == 0:
            amount = float(hostel.amount)
        elif i % 4 == 1:
            amount = round(float(hostel.amount) * 0.5)
        else:
            continue
        db.session.add(Payment(
            receipt_no=f"RCPT-{today.year}-{receipts:05d}", student_id=student.id,
            fee_record_id=hostel.id, amount=amount,
            paid_on=today - timedelta(days=30 - (i % 12)),
            method=methods[(i + 1) % 3], reference=f"TXN{800000 + i}",
        ))
        receipts += 1

    # previous-session payments so the 6-month chart has history
    for m in range(1, 6):
        base = today - timedelta(days=30 * m)
        student = students[m % len(students)]
        db.session.add(Payment(
            receipt_no=f"RCPT-{base.year}-{receipts:05d}", student_id=student.id,
            amount=12000 + m * 500, paid_on=base, method=methods[m % 3],
            reference=f"TXN{700000 + m}", note="Previous instalment",
        ))
        receipts += 1

    # ---- complaints ----------------------------------------------------
    for i, (category, subject, description, status, priority) in enumerate(COMPLAINTS):
        student = students[i % len(students)]
        created = datetime.utcnow() - timedelta(days=25 - i, hours=i)
        complaint = Complaint(
            ticket_no=f"TKT-{today.strftime('%y%m')}-{i + 1:04d}",
            student_id=student.id, category=category, subject=subject,
            description=description, status=status, priority=priority,
            created_at=created, updated_at=created + timedelta(hours=6),
            resolved_at=(created + timedelta(hours=30 + i * 3)) if status == "Resolved" else None,
        )
        db.session.add(complaint)
        db.session.flush()
        db.session.add(ComplaintResponse(
            complaint_id=complaint.id, author_id=None,
            message=RESPONSES[status], created_at=created + timedelta(hours=5),
        ))

    # ---- announcements -------------------------------------------------
    admin = User.query.filter_by(role="admin").first()
    for i, (title, body, tag, pinned) in enumerate(ANNOUNCEMENTS):
        db.session.add(Announcement(
            title=title, body=body, tag=tag, is_published=True, is_pinned=pinned,
            posted_by=admin.id if admin else None,
            created_at=datetime.utcnow() - timedelta(days=i * 2),
        ))

    # ---- staff ---------------------------------------------------------
    for name, role, shift, phone, email, notes in STAFF:
        db.session.add(Staff(
            full_name=name, role=role, shift=shift, phone=f"+91 {phone}",
            email=email or None, joined_on=today - timedelta(days=400), notes=notes,
        ))

    # ---- TQM artefacts -------------------------------------------------
    for module, description, category, s, o, d, status in DEFECTS:
        db.session.add(DefectLog(
            module=module, description=description, category=category,
            severity=s, occurrence=o, detection=d, status=status,
        ))
    for phase, title, detail in PDCA:
        db.session.add(PDCALog(phase=phase, title=title, detail=detail, owner="Warden"))

    # ---- welcome notifications ----------------------------------------
    for student in students[:5]:
        db.session.add(Notification(
            user_id=student.user_id, title="Welcome to the hostel portal",
            message="Your room allocation and fee details are now available.",
            icon="sparkles",
        ))

    db.session.commit()
    print(f"Demo data loaded: {len(rooms)} rooms, {len(students)} students, "
          f"{len(COMPLAINTS)} complaints, {len(STAFF)} staff.")
    print(f"Demo student login: 23CS1001@student.ujjwalhostel.edu.in / {DEMO_STUDENT_PASSWORD}")


if __name__ == "__main__":
    import os

    os.environ.setdefault("FLASK_APP", "app.py")
    from app import app  # noqa: E402

    with app.app_context():
        seed()
