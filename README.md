# Ujjwal Hostel Management System

A complete, responsive hostel management web application built with **Python / Flask**,
**SQLite** and vanilla HTML/CSS/JS (Chart.js + Lucide icons). It covers the full hostel
lifecycle: student registration and login, room and bed allocation, hostel fees and
payment receipts, complaints with an admin response workflow, announcements, staff
records, CSV reports — plus a Quality/TQM dashboard (Pareto, FMEA, PDCA) computed from
real complaint data.

> Academic project for **BBAT104 — Fundamentals of TQM** (baseline system: *Hostel
> Management System*, TQM goal: *optimise room allocation & complaint resolution*).
> Quality-goal features implemented: role-based login, strict validation, fast search &
> filters, dashboards and graphical reports, CSV export, audit trail, PDCA tracker.

---

## 1. Feature overview

**Public website**
- Landing page with hero, about, facilities gallery, live room availability (from the
  database — never hardcoded), hostel rules, notices, FAQ accordion and contact form.
- Student login, student registration and a separate administrator login.
- Light / dark theme toggle, fully responsive layout, accessible focus states.

**Student portal**
- Personalised dashboard: room, fee balance, next due date, open complaints, notices.
- My Profile — edit contact details, upload a photo, change password.
- My Room — room, bed, floor, capacity, roommates and allocation history.
- Fee Details and Payment History with printable receipts.
- Submit / track complaints (category, subject, description, optional photo or PDF,
  status timeline, admin replies).
- Announcements, hostel rules & FAQ, contact administration, in-app notifications.

**Administrator console**
- Overview with KPI cards and Chart.js analytics (fees, occupancy, complaint mix).
- Student management: add, search, filter, edit, deactivate, delete (blocked when
  financial history exists), reset password, individual student profiles.
- Room management: add/edit/archive rooms, capacity, type, floor, semester fee,
  maintenance status, colour-coded occupancy cards.
- Room allocation: assign a free bed, transfer between rooms, vacate, full history.
  **Capacity guards make over-allocation impossible.**
- Fee management: assign a fee to one student / a room / a year group / everyone,
  record payments (cash, UPI, bank transfer, other), auto receipt numbers.
- Payment records with search, method and date-range filters, CSV export.
- Complaint management: filter, change status, respond, plus the office inbox for
  contact-form messages. Resolution time is tracked automatically.
- Announcements (publish / unpublish / pin), staff directory, activity (audit) log,
  settings (hostel profile, fee default, registration toggle, admin accounts).
- Reports & analytics with occupancy, collection, dues, complaint charts and six CSV
  exports.
- Quality (TQM): Pareto analysis of complaint categories, FMEA/defect register with
  RPN scores, PDCA improvement log, CTQ metrics.

---

## 2. Technology stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| Framework | Flask 3 (application factory, blueprints) |
| ORM / DB | Flask-SQLAlchemy + SQLite (portable to PostgreSQL via `DATABASE_URL`) |
| Auth | Flask-Login (hashed passwords, role checks read from the DB) |
| Forms / CSRF | Flask-WTF `CSRFProtect` + server-side validation |
| Frontend | HTML5, custom CSS design system, vanilla JS |
| Charts / icons | Chart.js 4 and Lucide (both bundled locally in `hms/static/vendor`) |
| Fonts | Inter (bundled locally as a woff2 file) |

No Node, no build step, no CDN dependency — the app runs offline once installed.

---

## 3. Project structure

```
.
├── app.py                  # entry point — python app.py
├── seed_demo.py            # optional demo data loader
├── smoke_test.py           # end-to-end route/write-path test
├── requirements.txt
├── .env.example
├── instance/hostel.db      # SQLite database (created automatically)
├── docs/
│   └── TQM_REPORT.md       # FMEA, SIPOC, Pareto, fishbone, PDCA write-up
└── hms/
    ├── __init__.py         # app factory, filters, error pages, CLI commands
    ├── config.py           # environment-driven configuration
    ├── extensions.py       # db / login manager / csrf
    ├── models.py           # 16 relational tables
    ├── utils.py            # decorators, validation, uploads, CSV, audit log
    ├── blueprints/
    │   ├── public.py       # landing page + contact form
    │   ├── auth.py         # register, student login, admin login, logout
    │   ├── student.py      # student portal
    │   └── admin.py        # administrator console + exports
    ├── templates/          # Jinja2 templates (public, auth, student, admin)
    └── static/             # css, js, images, vendor libs, uploads
```

---

## 4. Installation

```bash
# 1. create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. install dependencies
pip install -r requirements.txt

# 3. configure environment (optional but recommended)
cp .env.example .env               # then edit SECRET_KEY
```

> Quick start without a `.env`: the app falls back to a development key and
> `instance/hostel.db`. **Set a real `SECRET_KEY` before showing this to anyone.**

---

## 5. Database initialisation

Tables are created automatically the first time the app starts. To do it explicitly:

```bash
flask --app app.py init-db
```

### Create the first administrator

Administrator accounts are **never hardcoded**. Create one from the CLI:

```bash
flask --app app.py create-admin
# prompts for name, email, password (min. 8 chars, letters + numbers)
```

or non-interactively:

```bash
flask --app app.py create-admin --name "Warden" --email warden@example.edu \
    --password "YourStrongPass1"
```

Further administrators can be added later from **Settings → Administrator accounts**.

### Optional demo data (for demonstration / viva only)

```bash
flask --app app.py seed-demo --yes
```

This loads 16 rooms, 18 students, fee records, payments, complaints, staff,
announcements and TQM entries. Manage/reset it any time:

```bash
rm instance/hostel.db                      # start from an empty database
flask --app app.py create-admin             # recreate your admin account
```

Demo logins created by the seeder (student accounts only):

| Role | Email | Password |
|---|---|---|
| Student | `23cs1001@student.ujjwalhostel.edu.in` | `Student@123` |
| Student | `23cs1002@student.ujjwalhostel.edu.in` | `Student@123` |

---

## 6. Running the website

```bash
python app.py
```

Open <http://127.0.0.1:5000>.

- Public website — `/`
- Student registration — `/auth/register`
- Student login — `/auth/login`
- Administrator login — `/auth/admin/login`

Set `PORT` and `FLASK_DEBUG` in `.env` to change the port or disable the reloader.
For production use a WSGI server, e.g. `gunicorn -w 3 app:app`, and set
`SESSION_COOKIE_SECURE=true` behind HTTPS.

---

## 7. Configuration reference (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Flask session signing key | insecure dev fallback |
| `DATABASE_URL` | SQLAlchemy URI (SQLite or PostgreSQL) | `sqlite:///instance/hostel.db` |
| `SESSION_MINUTES` | Session lifetime | `120` |
| `SESSION_COOKIE_SECURE` | HTTPS-only cookies | `false` |
| `WTF_CSRF_ENABLED` | CSRF protection toggle | `true` |
| `HOSTEL_NAME` | Fallback hostel name | `Ujjwal Hostel` |
| `STUDENT_SELF_REGISTRATION` | Allow public sign-up | `true` |
| `PORT` / `FLASK_DEBUG` | Dev server options | `5000` / `1` |

Hostel name, address, contact details, default fee and the self-registration switch can
also be edited at runtime from **Admin → Settings**.

---

## 8. Security notes

- Passwords are stored only as Werkzeug hashes; the plaintext is never persisted.
- Role checks (`admin_required`, `student_required`) read the user's role from the
  database session object — a POSTed `role` field is never trusted.
- Students can only ever load their own records; every query is scoped by
  `current_user.student` and foreign-key ownership is re-checked on detail routes.
- CSRF tokens are required on every POST form (`Flask-WTF CSRFProtect`).
- SQL access goes through the SQLAlchemy ORM (parameterised queries).
- Uploads are extension-whitelisted, size-capped (4 MB) and renamed with random tokens.
- Sessions are `HttpOnly` + `SameSite=Lax` (and `Secure` when configured).
- Money is `Numeric(10, 2)`; important multi-row operations run in one transaction and
  roll back on failure.
- An audit trail (`activity_logs`) records sign-ins and data changes.

> This project does **not** integrate a payment gateway, email or SMS provider. Payments
> shown are those recorded manually by hostel staff, and notifications are in-app only —
> the UI says so explicitly rather than implying otherwise.

---

## 9. Manual testing checklist

**Public**
- [ ] Landing page loads; room availability, resident and bed counts match **Admin → Rooms**.
- [ ] Contact form validates empty/short input and shows a success toast when sent.
- [ ] Theme toggle switches light/dark and survives a page reload.

**Authentication**
- [ ] Student registration rejects a duplicate email, a duplicate enrollment number,
      mismatched passwords and a weak password.
- [ ] Student cannot log in at `/auth/admin/login` ("does not have administrator privileges").
- [ ] Admin cannot log in at `/auth/login` (redirected to the admin login with a message).
- [ ] Visiting `/admin/...` while signed in as a student returns the 403 page.
- [ ] Logout clears the session; protected pages redirect to login.

**Student portal**
- [ ] Dashboard shows only that student's room, dues and complaints.
- [ ] Profile update saves; photo upload accepts JPG/PNG and rejects other types.
- [ ] Password change requires the current password and enforces the length rule.
- [ ] Fee list shows billed / paid / balance and correct statuses.
- [ ] Receipt opens, prints and shows the receipt number.
- [ ] Complaint submission requires a category, subject (≥5 chars) and description (≥15 chars);
      the ticket appears with status *Pending* and the admin receives a notification.

**Admin console**
- [ ] Overview KPI numbers equal the underlying lists (students, rooms, dues, complaints).
- [ ] Add student → the account can sign in with the chosen password.
- [ ] Search and filters (status, year, allocation, room type, method, dates) narrow results.
- [ ] Assign a bed → the student's portal shows the room, bed and roommates.
- [ ] Attempting to assign a bed to a full room is refused with a clear message.
- [ ] Transfer a student → old allocation closes, new one opens, history keeps both.
- [ ] Vacate a room → the bed becomes available again.
- [ ] Assign a fee to "all active students" → one row per student appears.
- [ ] Record a payment → receipt number generated, student balance drops, CSV export includes it.
- [ ] Deleting a student with payment history is blocked (deactivate instead).
- [ ] Complaint status change and reply reach the student's notification bell.
- [ ] Announcement publish/unpublish/pin reflected in the student portal.
- [ ] Staff add/edit/toggle works; role filter chips work.
- [ ] All six CSV exports download and open in a spreadsheet.
- [ ] Settings save; closing registration hides the public sign-up button.

**Quality / TQM**
- [ ] Pareto table counts equal the complaint counts in Complaint Management.
- [ ] Logging a defect computes RPN = S × O × D and sorts by risk.
- [ ] PDCA entries persist and display in order.

**Responsive / UX**
- [ ] Sidebar collapses to a drawer below 1024 px; the scrim closes it.
- [ ] Tables scroll horizontally on a phone; KPI cards stack in one column.
- [ ] Every visible button/link leads somewhere functional (no dead placeholders).

**Automated check**

```bash
python smoke_test.py     # exercises every route and the main write paths
```

---

## 10. Known limitations

- No online payment gateway (fees are recorded by staff — by design, and stated in the UI).
- No email/SMS delivery; notifications are in-app only.
- No password-reset email flow; administrators reset student passwords from the profile.
- Single-hostel scope (rooms carry blocks/floors rather than multiple hostel sites).
- SQLite suits a single-node academic deployment; switch `DATABASE_URL` to PostgreSQL
  for concurrent production use.

---

## 11. Documentation

- `docs/USER_MANUAL.md` — role-by-role guide (student + administrator) and troubleshooting.
- `docs/TQM_REPORT.md` — SIPOC, CTQ tree, FMEA matrix with RPN, Pareto analysis,
  fishbone diagram and PDCA log for the quality-goal features.
