# Ujjwal Hostel Management System — User Manual

A short, role-by-role guide to using the portal. (Developers: see `README.md` for
installation; TQM artefacts: `docs/TQM_REPORT.md`.)

---

## 1. Getting around

| Area | URL | Who |
|---|---|---|
| Public website | `/` | Everyone |
| Student registration | `/auth/register` | Prospective residents |
| Student login | `/auth/login` | Registered students |
| Administrator login | `/auth/admin/login` | Warden / office staff |
| Student portal | `/student/…` | Students only |
| Admin console | `/admin/…` | Administrators only |

Click the logo in the sidebar (or top-left of the public site) at any time to return to
the dashboard / homepage. The **moon/sun icon** switches light and dark mode; the choice is
remembered in the browser.

---

## 2. For students

### 2.1 Create an account
1. Open the homepage → **Apply for accommodation** (or **Student Login → Create account**).
2. Fill in your name, email, phone and **enrollment number** exactly as printed on your ID.
3. Pick course and year, optionally add guardian details and a profile photo.
4. Choose a password of at least 8 characters containing letters **and** numbers.
5. Submit — you land straight on your dashboard.

Registration is refused if the email or enrollment number is already in use.

### 2.2 Dashboard
Shows your room and bed (or “awaiting allocation”), fee balance, next due date, open
complaints and the latest hostel notices. The bell icon lists in-app notifications.

### 2.3 My Profile
Edit your email, phone, guardian details and address; upload a photo; change your password
(the current password is required). Name, enrollment number, course and year can only be
changed by the hostel office.

### 2.4 My Room
Room number, room type, floor, block, bed number, capacity, amenities, current occupancy,
your roommates and the full allocation history. Need a change? Use **Request room change**
or message the office.

### 2.5 Fees & payments
- **Fee Details** — each fee head with amount, paid, balance, due date and status
  (Pending / Partial / Paid / Overdue).
- **Payment History** — every recorded payment with its receipt number; click **Receipt** to
  open a printable copy.

> Payments are made at the hostel office (cash, UPI or bank transfer). The office records
> them and the receipt appears in your portal immediately. There is no online payment
> gateway in this system.

### 2.6 Complaints
1. **Submit Complaint** → choose a category (Electricity, Water Supply, Cleaning, Food
   Quality, Wi-Fi, Room Maintenance, Security, Other), subject (5+ characters), description
   (15+ characters), priority and an optional photo/PDF.
2. You receive a ticket number such as `TKT-2611-0004`.
3. Track the status — *Pending → In Progress → Resolved / Rejected* — and read the warden's
   replies. You can add replies to an open ticket.

### 2.7 Notices, rules and contact
Announcements carry a tag (General, Maintenance, Fees, Event, Holiday, Mess). **Hostel
Rules** lists house rules, the fee policy, FAQs and emergency extensions. **Contact
Administration** sends a message to the office inbox.

---

## 3. For administrators

### 3.1 First-time setup (one command)
```bash
flask --app app.py create-admin
```
Enter the name, email and a strong password. Additional administrators can be added later
in **Settings → Administrator accounts**. Change the password of any account from
**Settings → My password**.

### 3.2 Overview
KPI cards for active students, rooms, bed occupancy, fees collected, outstanding dues and
pending complaints — all computed from the database. Charts show six months of collection
vs billing, occupancy per room type and the complaint mix. Below them sit the latest
complaints, recent payments, room-status breakdown, upcoming due dates and the activity log.

### 3.3 Students
- **Add student** — creates the login and profile in one step; you can allocate a bed at the
  same time. Leave the password blank to use the default `Hostel@123` (tell the student to
  change it).
- **Search & filter** by name, email, phone, enrollment, course, status, year or allocation.
- **Open a profile** for fee records, payments, complaints, allocation history, password
  reset, room assign/transfer/vacate and account deactivation.
- **Delete** is only possible when no fee or payment history exists — otherwise deactivate,
  so financial records are preserved.

### 3.4 Rooms
Add a room with number, block, floor, type (Single/Double/Triple/Four sharing), bed capacity,
semester fee and amenities. Cards are colour-coded by live status: Available (green),
Partially occupied (amber), Full (blue), Maintenance (red). Use the wrench icon to park a
room in maintenance (only when empty) and the archive icon to retire it — archived rooms keep
their history.

### 3.5 Room allocation
Pick a student without a room, pick a room that has free beds, optionally choose the bed
number, and allocate. The system refuses any allocation that would exceed capacity or reuse
an occupied bed. Use ⇄ to transfer between rooms and the red button to vacate; every action
is recorded in the allocation history.

### 3.6 Fees and payments
- **Assign fee** to one student, all residents of a room, a year group, or every active
  student at once. Set the amount, due date and semester.
- **Record payment** with method (Cash, UPI, Bank Transfer, Other), date and reference. A
  receipt number (`RCPT-YYYY-NNNNN`) is generated automatically and the student is notified.
- Delete a fee record only while it has no payments; delete a payment only to correct a
  data-entry mistake (balances update instantly).

### 3.7 Complaints & messages
Filter by status or category, open a ticket, write a response and set the status. Students
are notified in-app on every change; resolution time is measured automatically. The
**Messages** page holds contact-form enquiries from the public website and messages students
send from their portal.

### 3.8 Announcements
Publish a notice with a tag; tick *Pin to top* for the important ones, or *Unpublish* to
hide it. Published notices appear on every student dashboard and announcement page, and
create an in-app notification. No email or SMS is sent.

### 3.9 Staff
Maintain the staff directory (Warden, Assistant Warden, Security, Cleaning, Maintenance, Mess
Manager) with contact details, shift and employment status. Filter by role or search by
name/phone/email.

### 3.10 Reports, quality and settings
- **Reports & analytics** — occupancy by room type, collection vs billing, collection by
  method, top pending dues, complaint performance, six CSV exports, and a Print button for a
  printable copy.
- **Quality (TQM)** — Pareto analysis of complaint categories with the 80 % threshold, a
  defect/FMEA register with RPN scores, PDCA log and CTQ metrics (resolution rate, average
  hours, tickets closed within 48 h).
- **Activity log** — every sign-in and data change with actor, entity, detail, IP and time.
- **Settings** — hostel name, tagline, address, contact details, office hours, default fee,
  late-fee note, self-registration switch, administrator accounts and your own password.

---

## 4. Troubleshooting

| Symptom | Reason / fix |
|---|---|
| “Invalid email or password” | Wrong credentials, or the account is still a demo account with its own password. |
| “Administrators must use the admin login” | Student and admin logins are deliberately separate. |
| “This account does not have administrator privileges” | The email belongs to a student account. |
| “Room … is full — occupancy can never exceed capacity” | Choose a room with free beds; the dropdown lists them. |
| “This student has fee or payment history …” | Deleting would destroy financial records — deactivate instead. |
| Empty dashboard / no rooms on the homepage | The database has no records yet: add rooms, students and fees from the console. |
| Changes not visible | Hard-refresh (Ctrl/Cmd + Shift + R); dashboard numbers are recomputed per request. |
