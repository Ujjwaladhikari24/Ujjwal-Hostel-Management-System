"""End-to-end smoke test — exercises every route and the main write paths.

    python smoke_test.py

Runs against a throw-away SQLite database in the system temp folder, so it never
touches instance/hostel.db (your real data stays intact).
"""
import os
import sys
import tempfile

TEST_DB = os.path.join(tempfile.gettempdir(), "hms_smoke.db")
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from hms import create_app  # noqa: E402
from hms.extensions import db  # noqa: E402
from hms.models import (Allocation, Complaint, FeeRecord, Payment, Room,  # noqa: E402
                        Student, User)
from seed_demo import seed  # noqa: E402

app = create_app()
app.config["WTF_CSRF_ENABLED"] = False

ADMIN_EMAIL = "warden@smoke.local"
ADMIN_PASSWORD = "SmokeTest123"

with app.app_context():
    db.create_all()
    admin = User(name="Smoke Warden", email=ADMIN_EMAIL, role="admin")
    admin.set_password(ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.commit()
    seed()

FAILS = []


def check(label, resp, expected=(200, 302)):
    ok = resp.status_code in expected
    print(f"{'PASS' if ok else 'FAIL'}  {resp.status_code:3d}  {label}")
    if not ok:
        FAILS.append((label, resp.status_code))
        body = resp.get_data(as_text=True)
        print("      ", body[:600].replace("\n", " ")[:600])
    return resp


def login(client, email, password, admin=False):
    url = "/auth/admin/login" if admin else "/auth/login"
    return client.post(url, data={"email": email, "password": password}, follow_redirects=True)


with app.app_context():
    admin_email = ADMIN_EMAIL
    student = Student.query.first()
    student_email = student.user.email
    print(f"admin={admin_email}  student={student_email}\n")

# ------------------------------------------------------------------ public
with app.test_client() as c:
    check("GET  /", c.get("/"))
    check("POST /contact", c.post("/contact", data={
        "name": "Visitor", "email": "v@example.com", "subject": "Hi",
        "message": "Do you have single rooms available next term?",
    }), expected=(302,))
    check("GET  /auth/login", c.get("/auth/login"))
    check("GET  /auth/register", c.get("/auth/register"))
    check("GET  /auth/admin/login", c.get("/auth/admin/login"))
    check("GET  /student/ (anon -> redirect)", c.get("/student/"), expected=(302,))
    check("GET  /admin/ (anon -> redirect)", c.get("/admin/"), expected=(302,))

    # student self-registration through the real form
    resp = c.post("/auth/register", data={
        "name": "Test Registrant", "email": "new.student@example.com",
        "phone": "+91 9811111111", "enrollment_no": "25ZZ9999", "course": "B.Tech",
        "department": "Computer Science", "year": "1st Year",
        "password": "Testpass123", "confirm_password": "Testpass123",
    }, follow_redirects=True)
    check("POST /auth/register (valid)", resp)
    assert b"Test Registrant" in resp.data or b"Welcome" in resp.data
    check("GET  /student/ (after register)", c.get("/student/"))
    check("GET  /student/profile", c.get("/student/profile"))
    check("GET  /student/room", c.get("/student/room"))
    check("GET  /student/fees", c.get("/student/fees"))
    check("GET  /student/payments", c.get("/student/payments"))
    check("GET  /student/complaints", c.get("/student/complaints"))
    check("GET  /student/announcements", c.get("/student/announcements"))
    check("GET  /student/rules", c.get("/student/rules"))
    check("GET  /student/contact", c.get("/student/contact"))
    check("GET  /student/notifications", c.get("/student/notifications"))
    check("GET  /admin/ as student (403)", c.get("/admin/"), expected=(403,))
    # submit a complaint
    resp = c.post("/student/complaints", data={
        "category": "Electricity", "subject": "Light not working in corridor",
        "description": "The corridor light outside my room has been off for two days.",
        "priority": "Normal",
    }, follow_redirects=True)
    check("POST /student/complaints", resp)
    # contact message
    check("POST /student/contact", c.post("/student/contact", data={
        "subject": "Room request", "message": "Could I get a lower floor room?",
    }, follow_redirects=True))
    check("POST /student/profile", c.post("/student/profile", data={
        "phone": "+91 9822222222", "email": "new.student@example.com",
        "guardian_name": "Parent", "guardian_phone": "+91 9833333333",
        "address": "Jaipur",
    }, follow_redirects=True))
    check("POST /student/profile/password", c.post("/student/profile/password", data={
        "current_password": "Testpass123", "new_password": "Testpass456",
        "confirm_password": "Testpass456",
    }, follow_redirects=True))
    check("GET  /auth/logout", c.get("/auth/logout"), expected=(302,))

# --------------------------------------------------------------- student
with app.test_client() as c:
    check("POST /auth/login (student)", login(c, student_email, "Student@123"))
    check("GET  /student/", c.get("/student/"))
    with app.app_context():
        cid = Complaint.query.filter_by(student_id=student.id).first().id
        pid = Payment.query.filter_by(student_id=student.id).first()
        pid = pid.id if pid else None
    check("GET  /student/complaints/<id>", c.get(f"/student/complaints/{cid}"))
    resp = c.post(f"/student/complaints/{cid}/reply", data={"message": "Any update on this?"},
                  follow_redirects=True)
    check("POST /student/complaints/<id> reply", resp)
    if pid:
        check("GET  /student/payments/<id>/receipt", c.get(f"/student/payments/{pid}/receipt"))
    check("POST /student/notifications read-all",
          c.post("/auth/notifications/read-all", follow_redirects=True))
    check("GET  /auth/logout", c.get("/auth/logout"), expected=(302,))
    # admin login must reject a student account (fresh session, no user signed in)
    check("POST /auth/admin/login (student creds -> rejected)",
          c.post("/auth/admin/login", data={"email": student_email, "password": "Student@123"}),
          expected=(200, 403))

# ----------------------------------------------------------------- admin
with app.test_client() as c:
    check("POST /auth/admin/login", login(c, admin_email, ADMIN_PASSWORD, admin=True))
    for url in [
        "/admin/", "/admin/activity", "/admin/students", "/admin/students/new",
        "/admin/rooms", "/admin/rooms/new", "/admin/allocations", "/admin/fees",
        "/admin/payments", "/admin/complaints", "/admin/messages",
        "/admin/announcements", "/admin/staff", "/admin/reports", "/admin/quality",
        "/admin/settings",
        "/admin/export/students.csv", "/admin/export/payments.csv",
        "/admin/export/dues.csv", "/admin/export/rooms.csv",
        "/admin/export/complaints.csv", "/admin/export/allocations.csv",
        "/admin/students?q=aarav", "/admin/students?status=Active&housed=no",
        "/admin/rooms?type=Double%20Sharing&status=Full",
        "/admin/payments?method=UPI", "/admin/complaints?status=Pending",
    ]:
        check(f"GET  {url}", c.get(url))

    with app.app_context():
        st = Student.query.filter(Student.status == "Active").first()
        sid = st.id
        room = Room.query.filter_by(room_number="A-102").first()
        rid = room.id
        alloc = Allocation.query.filter_by(is_active=True).first()
        aid = alloc.id
        comp = Complaint.query.first()
        comp_id = comp.id
        fee = next(f for f in FeeRecord.query.all() if f.balance > 0)
        fee_id = fee.id
        fee_student = fee.student_id
        pay = Payment.query.first()
        pay_id = pay.id
        from hms.models import Announcement, Staff
        ann_id = Announcement.query.first().id
        staff = Staff.query.first()
        staff_id = staff.id

    check(f"GET  /admin/students/{sid}", c.get(f"/admin/students/{sid}"))
    check(f"GET  /admin/students/{sid}/edit", c.get(f"/admin/students/{sid}/edit"))
    check(f"GET  /admin/rooms/{rid}/edit", c.get(f"/admin/rooms/{rid}/edit"))
    check(f"GET  /admin/complaints/{comp_id}", c.get(f"/admin/complaints/{comp_id}"))
    check(f"GET  /admin/payments/{pay_id}/receipt", c.get(f"/admin/payments/{pay_id}/receipt"))

    # a brand-new student through the admin form
    resp = c.post("/admin/students/new", data={
        "name": "Admin Created", "email": "admin.created@example.com",
        "phone": "+91 9844444444", "enrollment_no": "25AA0001", "course": "B.Sc",
        "department": "Physics", "year": "1st Year", "password": "Testpass789",
    }, follow_redirects=True)
    check("POST /admin/students/new", resp)

    # assign a fee to one student and record a payment
    check("POST /admin/fees/new (single)", c.post("/admin/fees/new", data={
        "title": "Library Caution Fee", "amount": "1500",
        "due_date": "2026-12-31", "semester": "2026-27",
        "target": "single", "student_id": str(fee_student),
    }, follow_redirects=True))
    check("POST /admin/payments/new", c.post("/admin/payments/new", data={
        "student_id": str(fee_student), "amount": "1000", "method": "UPI",
        "paid_on": "2026-11-01", "reference": "UPI-TEST-1",
    }, follow_redirects=True))

    # complaint handling
    check("POST /admin/complaints/<id> status+response", c.post(f"/admin/complaints/{comp_id}", data={
        "action": "respond", "status": "In Progress",
        "message": "Team has been informed, will update shortly.",
    }, follow_redirects=True))

    # announcements
    check("POST /admin/announcements", c.post("/admin/announcements", data={
        "title": "Test notice from smoke test", "body": "This verifies announcement publishing works.",
        "tag": "General", "is_published": "1",
    }, follow_redirects=True))
    check("POST /admin/announcements/<id>/edit", c.post(f"/admin/announcements/{ann_id}/edit", data={
        "title": "Updated notice title", "body": "Updated body text for the announcement.",
        "tag": "Fees", "is_published": "1",
    }, follow_redirects=True))
    check("POST /admin/announcements/<id>/toggle",
          c.post(f"/admin/announcements/{ann_id}/toggle", follow_redirects=True))

    # staff CRUD
    check("POST /admin/staff (add)", c.post("/admin/staff", data={
        "full_name": "Test Warden", "role": "Warden", "phone": "+91 9855555555",
        "email": "test.warden@example.com", "shift": "Morning", "status": "Active",
        "joined_on": "2026-01-01",
    }, follow_redirects=True))
    check("POST /admin/staff (edit)", c.post("/admin/staff", data={
        "staff_id": str(staff_id), "full_name": "Ramesh Iyer", "role": "Warden",
        "phone": "+91 9800000001", "status": "Active",
    }, follow_redirects=True))
    check("POST /admin/staff/<id>/toggle",
          c.post(f"/admin/staff/{staff_id}/toggle", follow_redirects=True))

    # room create + duplicate rejection
    resp = c.post("/admin/rooms/new", data={
        "room_number": "C-301", "block": "Block C", "floor": "3",
        "room_type": "Triple Sharing", "capacity": "3",
        "fee_per_semester": "35000", "status": "Available",
    }, follow_redirects=True)
    check("POST /admin/rooms/new", resp)
    resp = c.post("/admin/rooms/new", data={
        "room_number": "C-301", "room_type": "Triple Sharing", "capacity": "3",
        "fee_per_semester": "35000",
    })
    check("POST /admin/rooms/new (duplicate blocked)", resp, expected=(400,))

    # capacity guard: try to fill a room beyond capacity
    with app.app_context():
        full_room = Room.query.filter(Room.room_number == "A-101").first()  # single
        free_student = Student.query.filter(Student.status == "Active").all()
        free_student = next(s for s in free_student if not s.active_allocation) if any(
            not s.active_allocation for s in free_student) else None
        full_room_id = full_room.id
        free_student_id = free_student.id if free_student else None
    if free_student_id:
        resp = c.post("/admin/allocations/new", data={
            "student_id": str(free_student_id), "room_id": str(full_room_id),
        }, follow_redirects=True)
        check("POST /admin/allocations/new (over-capacity blocked)", resp)
        assert b"full" in resp.data.lower() or b"capacity" in resp.data.lower()
        # now allocate to a room that has space
        with app.app_context():
            room = next((r for r in Room.query.all() if r.free_beds > 0
                         and r.live_status != "Maintenance"), None)
            room_id = room.id if room else None
        if room_id:
            check("POST /admin/allocations/new (valid)", c.post("/admin/allocations/new", data={
                "student_id": str(free_student_id), "room_id": str(room_id),
            }, follow_redirects=True))

    check("POST /admin/allocations/<id>/vacate",
          c.post(f"/admin/allocations/{aid}/vacate", follow_redirects=True))
    check("POST /admin/settings (general)", c.post("/admin/settings", data={
        "form_kind": "general", "hostel_name": "Ujjwal Hostel",
        "academic_session": "2026–27", "hostel_tagline": "Smart Hostel Management.",
        "address": "Block C, University Campus, Jaipur", "contact_email": "office@ujjwalhostel.edu.in",
        "contact_phone": "+91 141 400 7788", "office_hours": "Mon – Sat, 9:00 AM – 5:30 PM",
        "default_fee": "48000", "late_fee_note": "Late fee of ₹500 applies after the due date.",
        "registration_open": "1",
    }, follow_redirects=True))
    check("POST /admin/quality (log defect)", c.post("/admin/quality", data={
        "kind": "defect", "module": "Smoke test", "description": "Test defect from smoke test",
        "category": "Software Code", "severity": "6", "occurrence": "3", "detection": "4",
        "status": "Open", "logged_on": "2026-11-01",
    }, follow_redirects=True))
    check("POST /admin/quality (pdca)", c.post("/admin/quality", data={
        "kind": "pdca", "phase": "Plan", "title": "Smoke test entry",
        "detail": "Verify PDCA logging works.", "owner": "QA",
    }, follow_redirects=True))
    check("POST /admin/messages/<id>/read", c.post("/admin/messages/1/read", follow_redirects=True))
    check("GET  /admin/students/1/delete (POST guard)",
          c.post("/admin/students/1/delete", follow_redirects=True))
    check("GET  /auth/logout", c.get("/auth/logout"), expected=(302,))

# ------------------------------------------------------------- 404 / 403
with app.test_client() as c:
    check("GET  /nope (404)", c.get("/nope"), expected=(404,))

print("\n" + ("ALL CHECKS PASSED" if not FAILS else f"{len(FAILS)} FAILURE(S): {FAILS}"))
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)  # clean up the throw-away database
sys.exit(1 if FAILS else 0)
