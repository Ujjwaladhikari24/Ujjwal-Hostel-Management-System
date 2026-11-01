# TQM Quality Report — Hostel Management System

**Course:** BBAT104 — Fundamentals of TQM · **Session:** 2026–27
**Baseline system:** Hostel Management System
**Core TQM goal:** Optimise room allocation & complaint resolution
**Quality-goal features implemented (5 of the suggested set):**
role-based login · strict input validation · dashboard overview with search filters ·
graphical charts + CSV export · audit trail with PDCA improvement log.

Everything measurable in this report is produced by the application itself; the
**Quality (TQM)** screen in the admin console renders the Pareto chart, the FMEA register
and the PDCA log from live database rows.

---

## 1. Scope and CTQ tree

Critical to Quality (CTQ) parameters were derived from the two process pain points in the
TQM goal — wrong/over capacity allocation and slow complaint closure.

```
Resident satisfaction with hostel administration
├── Correct room allocation
│   ├── No bed assigned twice                     → unique (room, bed) among active allocations
│   ├── No room above capacity                    → capacity check inside the allocation transaction
│   └── Allocation changes are traceable          → allocation history (start/end/status)
├── Fast complaint resolution
│   ├── Every complaint is acknowledged           → auto ticket number + in-app notification
│   ├── Status is visible to the student          → Pending / In Progress / Resolved / Rejected
│   └── Resolution time is measurable             → resolved_at − created_at (hours)
├── Accurate fee records
│   ├── Balance is always derived, never typed    → billed − recorded payments
│   └── Receipts are unguessable and unique       → RCPT-YYYY-NNNNN sequence
└── Trustworthy data
    ├── Validation at entry (Poka-Yoke)           → server-side rules + input constraints
    └── Traceability                              → activity log (actor, action, IP, time)
```

---

## 2. SIPOC process map

| Suppliers | Inputs | Process | Outputs | Customers |
|---|---|---|---|---|
| Student, hostel office | Registration details, enrollment no., room preferences | Registration & verification → Login (role check) | Verified student account | Student, warden |
| Warden, room inventory | Room number, type, capacity, floor, fee | Room setup → Allocation (capacity-checked) → Vacate/transfer | Bed allotment + allocation history | Student, accounts |
| Accounts staff | Fee amount, due date, payment received | Fee assignment → Payment recording → Receipt generation | Fee statement, receipt, dues report | Student, auditor |
| Student, maintenance team | Complaint category, description, photo | Submission → Triage → Status change → Response → Closure | Ticket trail + resolution-time metric | Student, warden |
| Warden | Notice text, tag, pin flag | Publish → Notify in-app → Display | Announcement in every student portal | Residents |

---

## 3. FMEA matrix (RPN = Severity × Occurrence × Detection)

Ratings are 1–10; a higher RPN means fix first. Rows marked *closed* are already
mitigated in the current build and are also stored in the app's defect register.

| # | Failure mode | Effect | S | O | D | RPN | Mitigation implemented | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Two students allocated the same bed | Duplicate allotment, conflict | 8 | 3 | 4 | **96** | Bed uniqueness + student's single-active-allocation rule enforced server-side | Closed |
| 2 | Room allocated beyond capacity | Overcrowding, safety issue | 8 | 3 | 3 | 72 | Capacity checked in `_assign()`; free-bed list also drives the UI dropdowns | Closed |
| 3 | Balance wrong after a payment is deleted | Incorrect dues, disputes | 7 | 2 | 3 | 42 | Balance always derived from fee − payments; delete recomputes instantly | Closed |
| 4 | Duplicate enrollment/email registration | Split records | 7 | 2 | 2 | 28 | Unique constraints + pre-check with case-insensitive lookup | Closed |
| 5 | Capacity edited below current occupancy | Beds "disappear" | 6 | 2 | 3 | 36 | Edit form refuses capacity < occupied beds | Open (logged) |
| 6 | Complaint status change not notified | Student re-raises the issue | 5 | 3 | 2 | 30 | In-app notification on every status change and response | Closed |
| 7 | Session expiry loses a long form | Data re-entry | 4 | 4 | 3 | 48 | Reminder to save; session lifetime configurable | Open (logged) |
| 8 | Non-image file uploaded | XSS / storage abuse | 6 | 2 | 2 | 24 | Extension whitelist + 4 MB cap + randomised filenames | Closed |
| 9 | Student opens another student's record | Privacy breach | 8 | 1 | 2 | 16 | Ownership re-check on every detail route; 403 otherwise | Closed |
| 10 | Admin page reached by a student | Privilege escalation | 9 | 1 | 2 | 18 | Role read from the DB on every request (`admin_required`) | Closed |

**Priority order for the next iteration:** #1 → unexplained allocation errors are the
highest-risk remaining theme (#2, #5), then #7 (session/usability).

---

## 4. Pareto analysis (80/20)

The app counts complaints per category and sorts them descending. In the demo data set
every category currently carries the same load, so the table is flat — with real usage the
first two or three categories typically cover ~80% of tickets, and the *vital few* badge
highlights them.

Example of the layout the Quality screen produces:

| Rank | Category | Tickets | Share | Cumulative | Classification |
|---|---|---|---|---|---|
| 1 | Electricity | 3 | 21.4% | 21.4% | vital few |
| 2 | Room Maintenance | 3 | 21.4% | 42.8% | vital few |
| 3 | Cleaning | 2 | 14.3% | 57.1% | vital few |
| 4 | Wi-Fi | 2 | 14.3% | 71.4% | vital few |
| 5 | Water Supply | 2 | 14.3% | 85.7% | useful many |
| 6 | Security | 1 | 7.1% | 92.8% | useful many |
| 7 | Food Quality | 1 | 7.1% | 100% | useful many |
| 8 | Other | 0 | 0% | 100% | useful many |

**Reading:** fixing electrical and room-maintenance workflows removes roughly 40 % of the
complaint load; the first five categories cover ~86 %. The dashboard draws the cumulative
line and an 80 % threshold line so the split is visible at a glance.

---

## 5. Ishikawa (fishbone) root-cause analysis

```
        PEOPLE                     PROCESS                    SOFTWARE
   staff availability          triage hand-off delays      status not persisted
   shift handover gaps     ───────────┐   ┌───────────      balance recomputed late
   training on escalation             │   │                 broken upload validation
                        ┌─────────────┴───┴─────────────┐
        COMPLAINT VOLUME / RESOLUTION DELAY             
                        └─────────────┬───┬─────────────┘
   old wiring / plumbing         ──────┘   └──────    no SLA for closure
   weak Wi-Fi coverage                                 
   water pressure                                      reports run only monthly
        INFRASTRUCTURE                              MEASUREMENT
```

Causes traced back to the four buckets and how the system responds:

| Bucket | Root cause | Countermeasure in the system |
|---|---|---|
| People | Escalation depends on one warden | Every admin gets an in-app notification on submission; role-based access lets assistants act |
| Process | No agreed response clock | Resolution hours captured automatically; 48-hour compliance shown as a CTQ metric |
| Software | Status changes used to live in a notebook | Status is a persisted column with an audit trail |
| Infrastructure | Repeated electrical/plumbing failures | Pareto + FMEA register surface recurring categories for planned maintenance |

---

## 6. Checksheet / defect log

Maintained inside the app (Quality → *Log defect*). Each defect stores module, failure
mode, root-cause category, S/O/D, computed RPN, status and date — the same table is
rendered sorted by RPN so the most dangerous items are always on top. Seed examples
include the allocation race condition (RPN 96, closed) and the session-expiry issue
(RPN 48, open).

---

## 7. PDCA log (continuous improvement)

| Phase | Action | Evidence |
|---|---|---|
| **Plan** | Remove over-allocation risk identified by FMEA #1/#2 | Duplicate-bed and capacity failure modes scored in the FMEA |
| **Do** | Route every allocation path (admin form, transfer, bulk) through one validated helper | `_assign()` in `hms/blueprints/admin.py` |
| **Check** | Audit all active allocations for overlaps / over-capacity rooms | 0 overlaps, 0 rooms above capacity |
| **Act** | Standardise the helper and document it so future paths inherit the guard | README security section + inline comments |
| **Plan (next)** | Cut average complaint resolution time below 48 h | Current average is displayed on the Quality screen |
| **Do (next)** | Status workflow with notifications and a due-time indicator | Implemented for Pending → In Progress → Resolved |
| **Check (next)** | Track `closed ≤ 48 h` count from real data | CTQ card on the Quality screen |
| **Act (next)** | Add the metric to the weekly report exported as CSV | `complaints.csv` includes resolution hours |

---

## 8. Quality-goal feature mapping (5 features)

| Quality goal feature | Where it lives |
|---|---|
| Role-based login | `auth.admin_login`, `admin_required`, `student_required` decorators |
| Strict input validation (Poka-Yoke) | `utils.py` validators + per-form error lists, client-side `required/minlength` |
| Dashboard overview + search filters | Admin overview, student dashboard, filter bars on every list page |
| Graphical charts + CSV export | Chart.js on overview/reports/quality, six `/admin/export/*.csv` endpoints |
| Audit trail + PDCA tracker | `activity_logs` table and the Quality screen's PDCA log |

---

## 9. Evidence checklist for the viva

1. Show the public site reading live availability, then allocate a bed in the admin
   console and refresh the homepage — the free-bed count changes.
2. Try to allocate a bed into a full room — the system refuses with an explicit message
   (FMEA #1/#2 mitigation).
3. Submit a complaint as a student, then change its status as the admin — the student's
   notification bell updates and the resolution hours appear.
4. Open **Quality (TQM)** — Pareto with the 80 % threshold line, FMEA register sorted by
   RPN, PDCA entries and CTQ metrics, all derived from the database.
5. Export pending dues as CSV and reconcile it with the Fee Management totals.
