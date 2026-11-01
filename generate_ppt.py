#!/usr/bin/env python3
"""Generate an 11-page white-theme PPT for the Ujjwal Hostel Management System
BBAT104 TQM course project, following the project-review notice (Review 1 + Review 2)."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
import copy

# ---------------------------------------------------------------- palette ---
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)
NAVY     = RGBColor(0x1F, 0x3A, 0x5F)   # titles / primary dark
ACCENT   = RGBColor(0x20, 0x53, 0x75)   # blue accent bar
ACCENT2  = RGBColor(0x2A, 0x9D, 0x8F)   # teal highlight
DARK     = RGBColor(0x33, 0x33, 0x33)   # body text
MUTED    = RGBColor(0x59, 0x59, 0x59)   # muted text
LIGHT    = RGBColor(0xF4, 0xF7, 0xFA)   # light panel
LIGHTER  = RGBColor(0xE8, 0xEF, 0xF5)   # table header
BORDER   = RGBColor(0xC6, 0xD2, 0xDE)   # subtle border
GREEN    = RGBColor(0x2E, 0x7D, 0x46)

FONT = "Calibri"

SW, SH = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.75)

prs = Presentation()
prs.slide_width = SW
prs.slide_height = SH
BLANK = prs.slide_layouts[6]

# --------------------------------------------------------------- helpers ---
def add_slide():
    return prs.slides.add_slide(BLANK)

def rect(slide, x, y, w, h, fill, line=None):
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(0.75)
    sp.shadow.inherit = False
    return sp

def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tb, tf

def set_run(r, text, size, color, bold=False, italic=False, name=FONT):
    r.text = text
    f = r.font
    f.name = name
    f.size = Pt(size)
    f.color.rgb = color
    f.bold = bold
    f.italic = italic

def para(tf, first=False):
    if first and not tf.paragraphs[0].runs:
        return tf.paragraphs[0]
    return tf.add_paragraph()

def add_text(tf, runs, size=14, color=DARK, bold=False, align=PP_ALIGN.LEFT,
             space_after=6, space_before=0, first=False, level=0, line=None):
    """runs: str or list of (text, dict) tuples."""
    p = para(tf, first=first)
    p.alignment = align
    p.space_after = Pt(space_after)
    p.space_before = Pt(space_before)
    p.level = level
    if isinstance(runs, str):
        runs = [(runs, {})]
    for text, opts in runs:
        r = p.add_run()
        set_run(r, text,
                size=opts.get("size", size),
                color=opts.get("color", color),
                bold=opts.get("bold", bold),
                italic=opts.get("italic", False))
    if line is not None:
        p.line_spacing = line
    return p

def content_header(slide, title, kicker=None, pageno=None):
    """Standard white-themed content slide header."""
    rect(slide, 0, 0, SW, SH, WHITE)  # background
    if kicker:
        _, tf = textbox(slide, MARGIN, Inches(0.32), SW - 2*MARGIN, Inches(0.3))
        add_text(tf, kicker.upper(), size=11, color=ACCENT2, bold=True,
                 space_after=0, first=True)
        ty = Inches(0.62)
    else:
        ty = Inches(0.42)
    _, tf = textbox(slide, MARGIN, ty, SW - 2*MARGIN, Inches(0.85))
    add_text(tf, title, size=27, color=NAVY, bold=True, space_after=0, first=True)
    # accent underline bar
    bar_w = Inches(1.6)
    rect(slide, MARGIN, ty + Inches(0.92), bar_w, Inches(0.045), ACCENT)
    rect(slide, MARGIN + bar_w, ty + Inches(0.92), Inches(0.12), Inches(0.045), ACCENT2)
    footer(slide, pageno)

def footer(slide, pageno=None):
    _, tf = textbox(slide, MARGIN, Inches(7.08), SW - 2*MARGIN - Inches(1.0), Inches(0.35))
    add_text(tf, "Ujjwal Hostel Management System  |  BBAT104 — Fundamentals of TQM  |  White Theme",
             size=9, color=MUTED, space_after=0, first=True)
    if pageno:
        _, tf2 = textbox(slide, SW - MARGIN - Inches(0.9), Inches(7.08), Inches(0.9), Inches(0.35))
        add_text(tf2, str(pageno), size=10, color=MUTED, bold=True,
                 align=PP_ALIGN.RIGHT, space_after=0, first=True)

def bullets(slide, items, x, y, w, h, size=14, gap=7, first=True, line=1.0):
    """items: list of (text_or_runs, level) or dict with opts."""
    _, tf = textbox(slide, x, y, w, h)
    for i, item in enumerate(items):
        if isinstance(item, tuple):
            text, lvl = item
        else:
            text, lvl = item, 0
        opts = {}
        if isinstance(text, dict):
            opts = text.get("opts", {})
            text = text["text"]
        bullet = "•  " if lvl == 0 else "–  "
        add_text(tf, bullet + text, size=size,
                 color=opts.get("color", DARK), bold=opts.get("bold", False),
                 space_after=gap,
                 first=(first and i == 0), level=lvl, line=line)
        if opts.get("space_after"):
            tf.paragraphs[-1].space_after = Pt(opts["space_after"])
    return tf

def panel(slide, x, y, w, h, title=None, fill=LIGHT, title_color=NAVY):
    rect(slide, x, y, w, h, fill)
    if title:
        _, tf = textbox(slide, x + Inches(0.18), y + Inches(0.14), w - Inches(0.36), Inches(0.4))
        add_text(tf, title, size=13, color=title_color, bold=True, space_after=0, first=True)
    return slide

def set_cell(cell, text, size=11, color=DARK, bold=False, fill=None, align=PP_ALIGN.LEFT):
    if fill is not None:
        cell.fill.solid()
        cell.fill.fore_color.rgb = fill
    cell.margin_left = Inches(0.08)
    cell.margin_right = Inches(0.08)
    cell.margin_top = Inches(0.03)
    cell.margin_bottom = Inches(0.03)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf = cell.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    set_run(r, text, size=size, color=color, bold=bold)

def style_table_borders(table, color=BORDER):
    # light borders via tcPr
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
                ln = tcPr.makeelement(qn(tag), {"w": "9525", "cap": "flat"})
                fill = ln.makeelement(qn("a:solidFill"), {})
                clr = ln.makeelement(qn("a:srgbClr"), {"val": "%02X%02X%02X" % (color[0], color[1], color[2])})
                fill.append(clr); ln.append(fill)
                # order matters: lnL, lnR, lnT, lnB
                tcPr.append(ln)

# =============================================================== SLIDE 1 ==
s = add_slide()
rect(s, 0, 0, SW, SH, WHITE)
# side accent panel
rect(s, 0, 0, Inches(0.35), SH, ACCENT)
rect(s, Inches(0.35), 0, Inches(0.07), SH, ACCENT2)

_, tf = textbox(s, Inches(1.0), Inches(1.55), SW - Inches(2.0), Inches(0.5))
add_text(tf, "BBAT104 — FUNDAMENTALS OF TOTAL QUALITY MANAGEMENT (TQM)",
         size=14, color=ACCENT, bold=True, space_after=0, first=True)

_, tf = textbox(s, Inches(1.0), Inches(2.15), SW - Inches(2.0), Inches(1.9))
add_text(tf, "Ujjwal Hostel Management System", size=44, color=NAVY, bold=True, space_after=6, first=True)
add_text(tf, "A complete, responsive Flask hostel-management web application",
         size=18, color=DARK, space_after=0)

rect(s, Inches(1.0), Inches(4.25), Inches(2.6), Inches(0.05), ACCENT)

info = [
    ("Baseline System", "Hostel Management System"),
    ("Core TQM Goal", "Optimise room allocation & complaint resolution"),
    ("Session", "Academic Session 2026–27 (70 raw marks)"),
    ("Presented by", "Ujjwal Adhikari"),
    ("Reviews", "Review 1 + Review 2  •  2-minute presentation"),
    ("Theme", "White"),
]
y = Inches(4.55)
for label, val in info:
    _, tf = textbox(s, Inches(1.0), y, Inches(2.1), Inches(0.42))
    add_text(tf, label, size=11.5, color=MUTED, bold=True, space_after=0, first=True)
    _, tf = textbox(s, Inches(3.3), y, SW - Inches(4.35), Inches(0.42))
    add_text(tf, val, size=13, color=NAVY, bold=True, space_after=0, first=True)
    y += Inches(0.52)

footer(s, 1)

# =============================================================== SLIDE 2 ==
s = add_slide()
content_header(s, "Problem Statement & Quality Objective",
               kicker="Review 1 — Setup & SRS", pageno=2)

panel(s, MARGIN, Inches(1.62), Inches(6.1), Inches(4.4), title="Problem Statement")
bullets(s, [
    "Hostel operations are still managed manually or with scattered records.",
    "Room and bed allocation is error-prone — duplicate allotments and over-capacity rooms occur.",
    "Complaints lack tracking, status visibility, and timely resolution.",
    "Fee dues and receipts are not systematically recorded or auditable.",
    "Result: resident dissatisfaction, safety risks, and administrative inefficiency.",
], MARGIN + Inches(0.25), Inches(2.25), Inches(5.6), Inches(3.6), size=13.5, gap=9)

panel(s, Inches(7.15), Inches(1.62), Inches(5.45), Inches(4.4), title="Quality Objective", fill=LIGHTER)
bullets(s, [
    "Optimise room allocation and complaint resolution using TQM principles.",
    "Targets: zero over-allocation, faster complaint turnaround, accurate fees.",
    "Built-in quality controls: role-based login, input validation, audit trail, Pareto/FMEA/PDCA.",
    "Measurable CTQs: allocation correctness, resolution time, fee balance accuracy.",
], Inches(7.4), Inches(2.25), Inches(4.95), Inches(3.6), size=13.5, gap=9)

# =============================================================== SLIDE 3 ==
s = add_slide()
content_header(s, "Scope & User Roles", kicker="Review 1 — Scope", pageno=3)

cols = [
    ("Scope of the system", [
        "Student registration & login",
        "Room & bed allocation with capacity guards",
        "Hostel fees, payments & printable receipts",
        "Complaints with admin response workflow",
        "Announcements, staff directory, in-app notifications",
        "CSV reports & Quality/TQM dashboard",
    ], ACCENT),
    ("User roles", [
        "Student — profile, room, fees, complaints, notifications",
        "Administrator — full CRUD, allocations, fees, complaints, reports, settings, TQM",
        "Public — landing page, notices, FAQ, contact form",
    ], NAVY),
]
x = MARGIN
for title, items, color in cols:
    panel(s, x, Inches(1.62), Inches(6.0), Inches(4.5), title=title, fill=LIGHT, title_color=color)
    bullets(s, [{"text": it, "opts": {"color": DARK}} for it in items],
            x + Inches(0.25), Inches(2.3), Inches(5.55), Inches(3.7), size=13, gap=8)
    x += Inches(6.25)

# =============================================================== SLIDE 4 ==
s = add_slide()
content_header(s, "SRS — Modules & Features", kicker="Review 1 — SRS", pageno=4)

# modules panel
panel(s, MARGIN, Inches(1.62), Inches(6.0), Inches(4.5), title="System Modules", title_color=ACCENT)
bullets(s, [
    "Public website — landing, facilities, rules, notices, FAQ, contact",
    "Auth — student registration/login, admin login, role-based access",
    "Student portal — dashboard, profile, room, fees, complaints",
    "Admin console — students, rooms, allocations, fees, complaints, staff",
    "Quality (TQM) dashboard — Pareto, FMEA, PDCA, CTQ metrics",
    "Reports & CSV exports — six exportable reports",
], MARGIN + Inches(0.25), Inches(2.3), Inches(5.55), Inches(3.7), size=13, gap=8)

panel(s, Inches(7.15), Inches(1.62), Inches(5.45), Inches(4.5), title="Key Quality Features", title_color=NAVY)
bullets(s, [
    "Role-based login & strict server-side validation",
    "Capacity guards make over-allocation impossible",
    "Auto receipt numbers; balance derived (billed − paid)",
    "Complaint status timeline + admin replies",
    "Fast search, filters & Chart.js dashboards",
    "Audit trail (activity log) + PDCA improvement log",
], Inches(7.4), Inches(2.3), Inches(4.95), Inches(3.7), size=13, gap=8)

# =============================================================== SLIDE 5 ==
s = add_slide()
content_header(s, "Initial UI & Workflow", kicker="Review 1 — UI / Workflow", pageno=5)

panel(s, MARGIN, Inches(1.62), Inches(6.0), Inches(4.5), title="Student Journey", title_color=ACCENT)
bullets(s, [
    "Register / log in → personalised dashboard (room, dues, complaints)",
    "View my room & roommates • pay fees • download receipt",
    "Submit & track a complaint with status timeline",
    "Read announcements, rules; contact administration",
], MARGIN + Inches(0.25), Inches(2.3), Inches(5.55), Inches(3.7), size=13, gap=8)

panel(s, Inches(7.15), Inches(1.62), Inches(5.45), Inches(4.5), title="Admin Journey", title_color=NAVY)
bullets(s, [
    "Login → overview KPI cards & charts",
    "Manage students, rooms, allocations, fees & complaints",
    "Record payments → auto receipts • export CSV reports",
    "Run Pareto / FMEA / PDCA quality analysis",
], Inches(7.4), Inches(2.3), Inches(4.95), Inches(3.7), size=13, gap=8)

# workflow arrow strip
rect(s, MARGIN, Inches(6.35), SW - 2*MARGIN, Inches(0.06), BORDER)
steps = ["Landing / Register", "Login (role-based)", "Dashboard & modules", "CRUD + TQM", "Reports / CSV"]
xs = MARGIN
w_step = (SW - 2*MARGIN - Inches(0.4*4)) / 5
for i, st in enumerate(steps):
    rect(s, xs, Inches(6.2), w_step, Inches(0.32), ACCENT if i % 2 == 0 else ACCENT2)
    _, tf = textbox(s, xs, Inches(6.225), w_step, Inches(0.28))
    add_text(tf, st, size=10.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER, space_after=0, first=True)
    if i < 4:
        _, tf = textbox(s, xs + w_step, Inches(6.27), Inches(0.32), Inches(0.2))
        add_text(tf, "▸", size=12, color=ACCENT, align=PP_ALIGN.CENTER, space_after=0, first=True)
    xs += w_step + Inches(0.4)

# =============================================================== SLIDE 6 ==
s = add_slide()
content_header(s, "Database / System Design", kicker="Review 1 — System Design", pageno=6)

_, tf = textbox(s, MARGIN, Inches(1.6), SW - 2*MARGIN, Inches(0.5))
add_text(tf, "Flask application factory + Flask-SQLAlchemy (SQLite by default; PostgreSQL via DATABASE_URL). "
             "16 relational tables; every write is transaction-scoped and audited.",
         size=13, color=DARK, space_after=0, first=True, line=1.15)

rows, cols = 5, 3
tbl_shape = s.shapes.add_table(rows, cols, MARGIN, Inches(2.35), SW - 2*MARGIN, Inches(3.1))
table = tbl_shape.table
table.columns[0].width = Inches(3.4)
table.columns[1].width = Inches(3.9)
table.columns[2].width = Inches(5.05)
headers = ["Module", "Key tables", "Design points"]
data = [
    ("Students & Auth", "users, students", "Role from DB (never trusted POST); hashed passwords"),
    ("Rooms & Allocation", "rooms, allocation_history", "Unique (room, bed); capacity checked inside transaction"),
    ("Fees & Payments", "fees, payments", "Balance = billed − paid; RCPT-YYYY-NNNNN receipts"),
    ("Complaints & TQM", "complaints, tqm_entries", "Ticket number, status timeline, resolution time, RPN"),
]
for j, h in enumerate(headers):
    set_cell(table.cell(0, j), h, size=12, color=WHITE, bold=True, fill=NAVY,
             align=PP_ALIGN.LEFT)
for i, row in enumerate(data, start=1):
    fill = WHITE if i % 2 else LIGHT
    for j, val in enumerate(row):
        set_cell(table.cell(i, j), val, size=11.5, color=DARK, fill=fill,
                 bold=(j == 0))
style_table_borders(table)

# =============================================================== SLIDE 7 ==
s = add_slide()
content_header(s, "Technology Stack", kicker="Review 1 — Setup", pageno=7)

stack = [
    ("Language", "Python 3.10+"),
    ("Framework", "Flask 3 — application factory, blueprints"),
    ("ORM / DB", "Flask-SQLAlchemy + SQLite (portable to PostgreSQL)"),
    ("Auth", "Flask-Login — hashed passwords, DB role checks"),
    ("Forms / CSRF", "Flask-WTF CSRFProtect + server-side validation"),
    ("Frontend", "HTML5, custom CSS design system, vanilla JS"),
    ("Charts / Icons", "Chart.js 4 + Lucide (bundled locally, no CDN)"),
    ("Fonts", "Inter (bundled locally as woff2)"),
]
x = MARGIN
y = Inches(1.75)
card_w = Inches(4.0)
card_h = Inches(0.78)
gap_x = Inches(0.22)
gap_y = Inches(0.16)
for i, (label, val) in enumerate(stack):
    cx = x + (i % 2) * (card_w + gap_x)
    cy = y + (i // 2) * (card_h + gap_y)
    rect(s, cx, cy, card_w, card_h, LIGHT)
    rect(s, cx, cy, Inches(0.07), card_h, ACCENT)
    _, tf = textbox(s, cx + Inches(0.22), cy + Inches(0.12), card_w - Inches(0.4), Inches(0.3))
    add_text(tf, label, size=11.5, color=ACCENT2, bold=True, space_after=0, first=True)
    _, tf = textbox(s, cx + Inches(0.22), cy + Inches(0.42), card_w - Inches(0.4), Inches(0.32))
    add_text(tf, val, size=12.5, color=DARK, bold=True, space_after=0, first=True)

_, tf = textbox(s, MARGIN, Inches(5.55), SW - 2*MARGIN, Inches(1.3))
add_text(tf, [("No Node, no build step, no CDN dependency — runs offline once installed. "
               "Responsive layout with sidebar drawer, focus states and light/dark theme toggle.",
               {})], size=13, color=DARK, space_after=0, first=True, line=1.2)

# =============================================================== SLIDE 8 ==
s = add_slide()
content_header(s, "CRUD & Core Features — Working Application",
               kicker="Review 2 — Core Features", pageno=8)

panel(s, MARGIN, Inches(1.62), Inches(6.0), Inches(4.5), title="Demonstrated CRUD", title_color=ACCENT)
bullets(s, [
    "Students: add, search, filter, edit, deactivate, delete (blocked if payment history)",
    "Rooms: add/edit/archive; colour-coded occupancy cards",
    "Allocation: assign free bed, transfer, vacate — full history",
    "Fees: assign to student / room / year group / everyone",
    "Payments: cash, UPI, bank transfer; auto receipt numbers",
    "Complaints: filter, change status, respond; resolution time tracked",
], MARGIN + Inches(0.25), Inches(2.3), Inches(5.55), Inches(3.7), size=13, gap=8)

panel(s, Inches(7.15), Inches(1.62), Inches(5.45), Inches(4.5), title="Aligned with Quality Goals", title_color=NAVY)
bullets(s, [
    "Input validation & audit trail (reliability)",
    "Fast search, filters & dashboard (performance)",
    "CSV export & graphical charts (reporting)",
    "Unique ID constraints, confirmation dialogs (no duplicates)",
    "Exception handling & friendly UI alerts (error handling)",
], Inches(7.4), Inches(2.3), Inches(4.95), Inches(3.7), size=13, gap=8)

# =============================================================== SLIDE 9 ==
s = add_slide()
content_header(s, "TQM / Quality Implementation", kicker="Quality Goal — TQM Tools", pageno=9)

panel(s, MARGIN, Inches(1.62), Inches(6.0), Inches(4.5), title="Core TQM Goal", title_color=ACCENT)
bullets(s, [
    "Optimise room allocation & complaint resolution",
    "Five quality features implemented: role-based login, strict validation, dashboard with filters, "
    "charts + CSV export, audit trail with PDCA log",
    "Pareto analysis of complaint categories (80/20)",
    "FMEA register with RPN = Severity × Occurrence × Detection",
    "PDCA improvement log & CTQ tree",
], MARGIN + Inches(0.25), Inches(2.3), Inches(5.55), Inches(3.7), size=13, gap=8)

# FMEA mini-table on right
panel(s, Inches(7.15), Inches(1.62), Inches(5.45), Inches(4.5), title="Top FMEA Risks (RPN)", title_color=NAVY)
tbl_shape = s.shapes.add_table(4, 3, Inches(7.35), Inches(2.35), Inches(5.05), Inches(2.9))
table = tbl_shape.table
table.columns[0].width = Inches(1.05)
table.columns[1].width = Inches(2.6)
table.columns[2].width = Inches(1.4)
for j, h in enumerate(["RPN", "Failure mode", "Status"]):
    set_cell(table.cell(0, j), h, size=10.5, color=WHITE, bold=True, fill=NAVY)
fmea = [
    ("96", "Duplicate bed allotment", "Closed"),
    ("72", "Room beyond capacity", "Closed"),
    ("48", "Session expiry loses form", "Open"),
]
for i, row in enumerate(fmea, start=1):
    fill = WHITE if i % 2 else LIGHT
    for j, val in enumerate(row):
        set_cell(table.cell(i, j), val, size=10.5, color=DARK, fill=fill,
                 bold=(j == 2), align=PP_ALIGN.CENTER if j in (0, 2) else PP_ALIGN.LEFT)
style_table_borders(table)

_, tf = textbox(s, Inches(7.35), Inches(5.4), Inches(5.05), Inches(0.6))
add_text(tf, "All RPN scores computed from live complaint data in the admin Quality screen.",
         size=10.5, color=MUTED, space_after=0, first=True, line=1.1)

# ============================================================= SLIDE 10 ==
s = add_slide()
content_header(s, "Demo Evidence & GitHub Health", kicker="Review 2 — Evidence", pageno=10)

items_left = [
    "GitHub repository initialised with ≥30 meaningful commits",
    "Comprehensive README.md + User Manual",
    "GitHub Issues used for tracking",
    "Working application ready for live demo",
    "Demo data: 16 rooms, 18 students, fees, complaints, staff",
    "Smoke tests exercise every route and main write paths",
]
panel(s, MARGIN, Inches(1.62), Inches(6.0), Inches(4.5), title="Artefacts", title_color=ACCENT)
bullets(s, items_left, MARGIN + Inches(0.25), Inches(2.3), Inches(5.55), Inches(3.7), size=13, gap=8)

panel(s, Inches(7.15), Inches(1.62), Inches(5.45), Inches(4.5), title="2-Minute Demo Flow", title_color=NAVY)
bullets(s, [
    "Login (student / admin)",
    "Allocate a bed with capacity guard",
    "Record a payment → auto receipt",
    "File a complaint → admin responds",
    "Open TQM dashboard: Pareto & FMEA",
], Inches(7.4), Inches(2.3), Inches(4.95), Inches(3.7), size=13, gap=8)

# KPI strip
kpis = ["16 Rooms", "18 Students", "Zero Over-allocation", "TQM Dashboard"]
xs = MARGIN
w_k = Inches(2.95)
for i, k in enumerate(kpis):
    rect(s, xs, Inches(6.35), w_k, Inches(0.62), LIGHT)
    rect(s, xs, Inches(6.35), w_k, Inches(0.07), ACCENT2)
    _, tf = textbox(s, xs + Inches(0.18), Inches(6.5), w_k - Inches(0.36), Inches(0.4))
    add_text(tf, k, size=13.5, color=NAVY, bold=True, align=PP_ALIGN.CENTER, space_after=0, first=True)
    xs += w_k + Inches(0.15)

# =============================================================== SLIDE 11 ==
s = add_slide()
rect(s, 0, 0, SW, SH, WHITE)
rect(s, 0, 0, SW, Inches(0.14), ACCENT)
rect(s, 0, SH - Inches(0.14), SW, Inches(0.14), ACCENT2)

_, tf = textbox(s, MARGIN, Inches(1.9), SW - 2*MARGIN, Inches(1.6))
add_text(tf, "Thank You", size=40, color=NAVY, bold=True, align=PP_ALIGN.CENTER, space_after=4, first=True)
add_text(tf, "Ujjwal Hostel Management System — BBAT104 TQM Course Project",
         size=16, color=ACCENT, bold=True, align=PP_ALIGN.CENTER, space_after=8)
add_text(tf, "Optimising room allocation & complaint resolution through quality-by-design",
         size=13, color=DARK, align=PP_ALIGN.CENTER, space_after=0)

_, tf = textbox(s, MARGIN, Inches(4.1), SW - 2*MARGIN, Inches(1.0))
add_text(tf, [("Questions & discussion", {"bold": True, "color": NAVY, "size": 13}),
              ("   •  Working application demo  •  SRS / documentation  •  GitHub repository",
               {"color": DARK, "size": 12})], align=PP_ALIGN.CENTER, space_after=0, first=True, line=1.3)

footer(s, 11)

# ---------------------------------------------------------------- save ---
OUT = "/home/user/Ujjwal-Hostel-Management-System/Ujjwal_Hostel_Management_System_TQM_Presentation.pptx"
prs.save(OUT)
print("Saved:", OUT, "slides:", len(prs.slides._sldIdLst))
