
import os
import csv
import io
import smtplib
from threading import active_count
import pandas as pd
from email.message import EmailMessage
from email.mime.text import MIMEText
from collections import defaultdict
import smtplib
import matplotlib
matplotlib.use("Agg")

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas



from flask import (
    Flask,
    request,
    render_template,
    send_file,
    flash,
    redirect,
    url_for,
    session,
    render_template_string,
)



  # Change in production


# ------------------------------------------------------------
# BRANCH MAP
# ------------------------------------------------------------

BRANCH_MAP = {
    "05": "CSE",
    "04": "ECE",
    "03": "ME",
    "02": "EEE",
    "01": "CIV",
    "12": "IT",
    "66": "CSM",
    "67": "CSD"
}


# ------------------------------------------------------------
# MODELS
# ------------------------------------------------------------
# app.py — Final Version (UNLIMITED BRANCH PAIR PATTERN + PER-BRANCH EXAMS)
# ------------------------------------------------------------

import os, csv, json, zipfile
from collections import defaultdict
from flask import Flask, request, render_template, send_file, flash, redirect, url_for
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

import data_manager
import pdf_generator


app = Flask(__name__)
app.secret_key = "dev-secret-key"

# -------------------------
# CLASSES
# -------------------------

class Student:
    def __init__(self, roll, branch, year, subject=""):
        self.roll = roll
        self.branch = branch
        self.year = year
        self.subject = subject



class Seat:
    def __init__(self, seat_id, room, r, c):
        self.seat_id = seat_id
        self.room = room
        self.r = r
        self.c = c


def decode_rollno(rollno):
    rollno = rollno.strip()

    branch_code = rollno[6:8]
    branch = BRANCH_MAP.get(branch_code, "UNKNOWN")

    admission_year = int(rollno[:2])

    year_map = {
        22: 4,
        23: 3,
        24: 2,
        25: 1,
    }

    return branch, year_map.get(admission_year)


def validate_csv_header(reader):
    expected = {"rollno", "exam"}
    actual = set(reader.fieldnames or [])
    return actual == expected


def parse_students_csv(file):
    students = []
    errors = []

    reader = csv.DictReader(file)

    if not validate_csv_header(reader):
        return students, ["Invalid CSV header. Must contain: rollno, exam"]

    for i, row in enumerate(reader, start=2):
        rollno = row.get("rollno", "").strip()
        exam = row.get("exam", "").strip()

        if not rollno:
            errors.append(f"Row {i}: Missing rollno")
            continue

        if not exam:
            errors.append(f"Row {i}: Missing exam")
            continue

        try:
            branch, year = decode_rollno(rollno)
        except:
            errors.append(f"Row {i}: Invalid rollno format")
            continue

        students.append(Student(rollno, branch, year, exam))

    return students, errors


def group_students(students):
    groups = defaultdict(list)

    for s in students:
        key = f"{s.branch}_Y{s.year}"
        groups[key].append(s)

    for k in groups:
        groups[k].sort(key=lambda x: x.roll)

    return groups


# ------------------------------------------------------------
# SEATING LOGIC (UNCHANGED CORE)
# ------------------------------------------------------------
def is_safe(seat_map, room_id, r, c, branch):
    directions = [(-1,0),(1,0),(0,-1),(0,1)]

    for dr, dc in directions:
        key = (room_id, r+dr, c+dc)
        if key in seat_map and seat_map[key].branch == branch:
            return False
    return True

def generate_seating(groups, exams_for_branch, rooms):

    sorted_branches = sorted(
        groups.keys(), key=lambda b: len(groups[b]), reverse=True
    )

    next_index = {br: 0 for br in sorted_branches}
    assigns = {}
    seats = []
    seat_map = {}

    def rotated_branches(branches, shift):
        if not branches:
            return branches
        shift %= len(branches)
        return branches[shift:] + branches[:shift]

    for room in rooms:
        room_no = room["room_no"]
        rows = room["rows"]
        cols = room["cols"]
        room_id = f"R{room_no}"

        for c in range(cols):
            for r in range(rows):

                seat_id = f"{room_id}-{r}-{c}"
                seat_obj = Seat(seat_id, room_id, r, c)
                seats.append(seat_obj)

                left_key = (room_id, r, c - 1)
                front_key = (room_id, r - 1, c)
                diag_left_key = (room_id, r - 1, c - 1)
                diag_right_key = (room_id, r - 1, c + 1)

                active_branches = [
                    br for br in sorted_branches
                    if next_index[br] < len(groups[br])
                ]

                if not active_branches:
                    continue

                active_count = len(active_branches)

                # 🔥 4 BRANCH GRID LOGIC
                if active_count == 4:
                    b1, b2, b3, b4 = active_branches[:4]

                    if r % 2 == 0 and c % 2 == 0:
                        chosen_branch = b1
                    elif r % 2 == 0:
                        chosen_branch = b3
                    elif c % 2 == 0:
                        chosen_branch = b2
                    else:
                        chosen_branch = b4

                    if next_index[chosen_branch] < len(groups[chosen_branch]):
                        stu = groups[chosen_branch][next_index[chosen_branch]]
                        stu.subject = exams_for_branch.get(chosen_branch, "")

                        assigns[stu.roll] = seat_obj
                        seat_map[(room_id, r, c)] = stu
                        next_index[chosen_branch] += 1

                    continue

                # 🔥 NORMAL LOGIC
                branch_try_order = rotated_branches(active_branches, c)

                for try_branch in branch_try_order:
                    if next_index[try_branch] >= len(groups[try_branch]):
                        continue

                    stu = groups[try_branch][next_index[try_branch]]
                    stu.subject = exams_for_branch.get(try_branch, "")

                    if active_count in (2, 3):
                        if left_key in seat_map and seat_map[left_key].branch == stu.branch:
                            continue
                        if front_key in seat_map and seat_map[front_key].branch == stu.branch:
                            continue

                    elif active_count >= 5:
                        if left_key in seat_map and seat_map[left_key].branch == stu.branch:
                            continue
                        if front_key in seat_map and seat_map[front_key].branch == stu.branch:
                            continue
                        if diag_left_key in seat_map and seat_map[diag_left_key].branch == stu.branch:
                            continue
                        if diag_right_key in seat_map and seat_map[diag_right_key].branch == stu.branch:
                            continue

                    assigns[stu.roll] = seat_obj
                    seat_map[(room_id, r, c)] = stu
                    next_index[try_branch] += 1
                    break

    return assigns, seats
# -------------------------
# SEATING LOGIC (V2)
# -------------------------

def generate_branch_pairs(branches):
    pairs = []
    i = 0
    while i < len(branches):
        if i+1 < len(branches):
            pairs.append((branches[i], branches[i+1]))
        else:
            pairs.append((branches[i], None))
        i += 2
    return pairs

def generate_seating_v2(all_students, room_list):
    """
    all_students: list of Student objects (with subject assigned)
    room_list: list of room dicts from DB
    """
    
    # 1. Group students by branch
    groups = defaultdict(list)
    for s in all_students:
        groups[s.branch].append(s)
    
    # Sort students in each group by roll
    for br in groups:
        groups[br].sort(key=lambda x: x.roll)
        
    sorted_branches = sorted(groups.keys(), key=lambda b: len(groups[b]), reverse=True)
    branch_pairs = generate_branch_pairs(sorted_branches)
    num_pairs = len(branch_pairs)
    
    if num_pairs == 0:
        return {}, []

    next_index = {br: 0 for br in sorted_branches}
    assigns = {}
    seats = []

    seat_map = {}

    for room in rooms:

        room_no = room["room_no"]
        rows = room["rows"]
        cols = room["cols"]
        room_id = f"R{room_no}"

        # Select max 4 branches for this room
        # ✅ pick top 4 branches that still have students left
        room_branches = [
            br for br in sorted_branches
            if next_index[br] < len(groups[br])
        ][:4]
        
           # 🔥 shift for next room

        if not room_branches:
            continue

        for c in range(cols):
            for r in range(rows):

                seat_id = f"{room_id}-{r}-{c}"
                seat_obj = Seat(seat_id, room_id, r, c)
                seats.append(seat_obj)

                left_key = (room_id, r, c - 1)
                front_key = (room_id, r - 1, c)

                active_branches = [
                    br for br in room_branches
                    if next_index[br] < len(groups[br])
                ]

                if not active_branches:
                    break

                active_count = len(active_branches)

                # CASE 1: ONLY ONE BRANCH
                if active_count == 1:

                    br = active_branches[0]
                    stu = groups[br][next_index[br]]
                    stu.subject = exams_for_branch.get(br, "")

                    assigns[stu.roll] = seat_obj
                    seat_map[(room_id, r, c)] = stu
                    next_index[br] += 1
                    continue

                # CASE 2 OR 3 BRANCHES
                if active_count in (2,3):

                    assigned = False

                    for try_branch in active_branches:

                        if next_index[try_branch] >= len(groups[try_branch]):
                            continue

                        stu = groups[try_branch][next_index[try_branch]]
                        stu.subject = exams_for_branch.get(try_branch, "")

                        if left_key in seat_map and seat_map[left_key].branch == stu.branch:
                            continue

                        if front_key in seat_map and seat_map[front_key].branch == stu.branch:
                            continue

                        assigns[stu.roll] = seat_obj
                        seat_map[(room_id, r, c)] = stu
                        next_index[try_branch] += 1
                        assigned = True
                        break

                    if not assigned:
                        for try_branch in active_branches:
                            if next_index[try_branch] < len(groups[try_branch]):
                                stu = groups[try_branch][next_index[try_branch]]
                                assigns[stu.roll] = seat_obj
                                seat_map[(room_id, r, c)] = stu
                                next_index[try_branch] += 1
                                break

                    continue

                # CASE 4 BRANCHES
                # CASE 4 BRANCHES
                if active_count == 4:

                    assigned = False

                    # try all branches safely
                    for try_branch in active_branches:

                        if next_index[try_branch] >= len(groups[try_branch]):
                            continue

                        if not is_safe(seat_map, room_id, r, c, try_branch):
                            continue

                        stu = groups[try_branch][next_index[try_branch]]
                        stu.subject = exams_for_branch.get(try_branch, "")

                        assigns[stu.roll] = seat_obj
                        seat_map[(room_id, r, c)] = stu
                        next_index[try_branch] += 1
                        assigned = True
                        break                   
# fallback (if no safe option)
                    if not assigned:
                        for try_branch in active_branches:
                            if next_index[try_branch] < len(groups[try_branch]):
                                stu = groups[try_branch][next_index[try_branch]]
                                assigns[stu.roll] = seat_obj
                                seat_map[(room_id, r, c)] = stu
                                next_index[try_branch] += 1
                                break
    return assigns, seats 
# ------------------------------------------------------------
# FILE OUTPUT
# ------------------------------------------------------------

def write_assignments_csv(assigns, students_map, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["roll", "branch", "subject", "room", "row", "col"])

        for roll, st in students_map.items():
            if roll in assigns:
                seat = assigns[roll]
                w.writerow([roll, st.branch, st.subject, seat.room, seat.r, seat.c])


def generate_room_pdf_exact_layout(room_id, seats, assigns, students_map, out_path):
    from reportlab.lib.pagesizes import A4, landscape

    c = canvas.Canvas(out_path, pagesize=landscape(A4))
    width, height = landscape(A4)


    # -------------------------
    # HEADER
    # -------------------------
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, height - 2 * cm, "VARDHAMAN COLLEGE OF ENGINEERING")

    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, height - 2.7 * cm, "EXAM SEATING ARRANGEMENT")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, height - 3.6 * cm, f"Room No: {room_id}")

    c.setFont("Helvetica", 9)
    c.drawRightString(width - 2 * cm, height - 3.6 * cm, "Mid / Semester Examination")

    # -------------------------
    # SEATING GRID CONFIG
    # -------------------------
    start_x = 2 * cm
    start_y = height - 5 * cm

    rows = max(s.r for s in seats) + 1
    cols = max(s.c for s in seats) + 1

    cell_w = 2.6 * cm
    cell_h = 1.4 * cm


    # -------------------------
    # DRAW GRID
    # -------------------------
    c.setStrokeColor(colors.black)

    for r in range(rows + 1):
        c.line(
            start_x,
            start_y - r * cell_h,
            start_x + cols * cell_w,
            start_y - r * cell_h,
        )

    for c_idx in range(cols + 1):
        c.line(
            start_x + c_idx * cell_w,
            start_y,
            start_x + c_idx * cell_w,
            start_y - rows * cell_h,
        )

    # -------------------------
    # FILL SEATS
    # -------------------------
    c.setFont("Helvetica", 7)

    for roll, seat in assigns.items():
        if seat.room != room_id:
            continue

        s = students_map[roll]

        x = start_x + seat.c * cell_w + 0.1 * cm
        y = start_y - seat.r * cell_h - 0.5 * cm

        c.drawString(x, y, roll)
        c.drawString(x, y - 0.35 * cm, s.subject)

    # -------------------------
    # BRANCH / YEAR SUMMARY
    # -------------------------
    summary = defaultdict(lambda: defaultdict(int))

    for roll, seat in assigns.items():
        if seat.room != room_id:
            continue
        s = students_map[roll]
        summary[s.branch][s.year] += 1

    table_y = start_y - rows * cell_h - 1.2 * cm

    c.setFont("Helvetica-Bold", 9)
    c.drawString(2 * cm, table_y, "BRANCH / YEAR SUMMARY")

    table_y -= 0.6 * cm
    c.setFont("Helvetica", 8)

    x = 2 * cm
    for branch in sorted(summary.keys()):
        y = table_y
        c.drawString(x, y, branch)
        for year in sorted(summary[branch].keys()):
            y -= 0.45 * cm
            c.drawString(x, y, f"Y{year} : {summary[branch][year]}")
        x += 3.2 * cm

    # -------------------------
    # INVIGILATOR SECTION
    # -------------------------
    sign_y = 2.2 * cm

    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, sign_y, "Invigilator Name:")
    c.line(6 * cm, sign_y - 0.1 * cm, 14 * cm, sign_y - 0.1 * cm)

    c.drawString(2 * cm, sign_y - 1 * cm, "Signature:")
    c.line(6 * cm, sign_y - 1.1 * cm, 14 * cm, sign_y - 1.1 * cm)

    # -------------------------
    # FINALIZE
    # -------------------------
    c.showPage()
    c.save()


# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------

@app.route("/")
def step1():
    return render_template("step1.html")

@app.route("/popup")
def popup():
    return render_template("popup.html")


@app.route("/generate", methods=["POST"])
def generate():

    files = request.files.getlist("students_csv")

    if not files:
        flash("Please upload at least one CSV file")
        return redirect(url_for("step1"))

    all_students = []
    all_errors = []

    for file in files:
        if not file.filename.endswith(".csv"):
            all_errors.append(f"{file.filename}: Not a CSV")
            continue

        text_file = io.TextIOWrapper(file.stream, encoding="utf-8")
        students, errors = parse_students_csv(text_file)

        all_students.extend(students)
        all_errors.extend(errors)

    if all_errors:
        for e in all_errors:
            flash(e)
        return redirect(url_for("step1"))

    if not all_students:
        flash("No valid students found")
        return redirect(url_for("step1"))

    students = all_students

    exams_for_branch = {
        f"{s.branch}_Y{s.year}": s.subject for s in students
    }

    rooms = []

    form = request.form.to_dict(flat=False)

    for key in form:
        if key.endswith("[selected]"):
            idx = key.split("[")[1].split("]")[0]

            room_no = int(form[f"rooms[{idx}][room_no]"][0])
            rows = int(form[f"rooms[{idx}][rows]"][0])
            cols = int(form[f"rooms[{idx}][cols]"][0])

            rooms.append({
                "room_no": room_no,
                "rows": rows,
                "cols": cols
            })

    groups = group_students(students)
    assigns, seats = generate_seating(groups, exams_for_branch, rooms)

    students_map = {s.roll: s for s in students}

    os.makedirs("static", exist_ok=True)

    write_assignments_csv(assigns, students_map,
                          "static/assignments.csv")

    rooms_by_id = defaultdict(list)

    for s in seats:
        rooms_by_id[s.room].append(s)

    room_pdfs = []

    for room_id, room_seats in rooms_by_id.items():
        pdf_path = f"static/{room_id}.pdf"
        generate_room_pdf_exact_layout(
        room_id=room_id,
        seats=room_seats,
        assigns=assigns,
        students_map=students_map,
        out_path=pdf_path
        )
        room_pdfs.append(f"{room_id}.pdf")

    result = {
        "assigned": len(assigns),
        "total": len(students),
        "room_pdfs": room_pdfs
    }

    return render_template("index.html", result=result)


@app.route("/download_assignments")
def download_assignments():
    return send_file("static/assignments.csv",
                     as_attachment=True)


# ================= FACULTY MAIL SYSTEM =================

@app.route("/faculty", methods=["POST"])
def faculty_upload():

    file = request.files.get("faculty_csv")

    if not file or not file.filename.endswith(".csv"):
        return "Invalid file"

    text_file = io.TextIOWrapper(file.stream, encoding="utf-8")
    ok, result = validate_faculty_csv(text_file)

    if not ok:
        return result

    session["faculty_preview"] = result

    return "Faculty CSV Uploaded Successfully"

@app.route("/send-faculty-mails", methods=["POST"])
def send_faculty_mails():

    preview = session.get("faculty_preview")

    if not preview:
        return "No data found"

    for row in preview:

        email = str(row.get("email", "")).strip()

        # ❌ skip invalid values
        if email == "" or email.lower() == "nan" or "@" not in email:
            continue

        send_invigilation_email(
            email,
            str(row.get("faculty_name", "")),
            str(row.get("branch", "")),
            str(row.get("exam_date", "")),
            str(row.get("exam_time", ""))
        )

    return "Emails sent successfully"


REQUIRED_COLUMNS = [
    'faculty_id',
    'faculty_name',
    'branch',
    'email',
    'exam_date',
    'exam_time'
]

VALIDATED_FILE = "validated.csv"

@app.route("/faculty")
def faculty_home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>Examination Cell - Invigilation Mail System</title>
<style>
*{
    margin:0;
    padding:0;
    box-sizing:border-box;
    font-family: 'Segoe UI', sans-serif;
}

body{
    height:100vh;
    background: linear-gradient(135deg,#e3f2fd,#bbdefb,#90caf9);
    display:flex;
    flex-direction:column;
    align-items:center;
}

/* HEADER */
.header{
    width:100%;
    padding:25px;
    text-align:center;
    background: rgba(255,255,255,0.25);
    backdrop-filter: blur(8px);
    box-shadow:0 4px 15px rgba(0,0,0,0.1);
}

.header h1{
    font-size:28px;
    color:#0d47a1;
}

.header p{
    font-size:16px;
    color:#1565c0;
}

/* CARD */
.card{
    margin-top:80px;
    width:420px;
    padding:40px;
    border-radius:20px;
    background: rgba(255,255,255,0.6);
    backdrop-filter: blur(15px);
    box-shadow:0 15px 35px rgba(0,0,0,0.15);
    text-align:center;
    transition:0.3s;
}

.card:hover{
    transform:translateY(-5px);
}

.card h2{
    margin-bottom:20px;
    color:#0d47a1;
}

/* FILE INPUT */
input[type=file]{
    margin:20px 0;
    padding:10px;
    border-radius:8px;
    border:1px solid #90caf9;
    width:100%;
}

/* BUTTON */
button{
    width:100%;
    padding:12px;
    border:none;
    border-radius:10px;
    background: linear-gradient(135deg,#1976d2,#42a5f5);
    color:white;
    font-weight:bold;
    cursor:pointer;
    transition:0.3s;
}

button:hover{
    transform:scale(1.05);
    box-shadow:0 8px 20px rgba(0,0,0,0.2);
}

.footer{
    margin-top:auto;
    padding:15px;
    font-size:13px;
    color:#0d47a1;
}

.logo {
  height: 85px;
  width: auto;
}
</style>
</head>
<body>

<div class="header">
 <h1>Vardhaman College of Engineering</h1>
    <h2>An Autonomous Institution, Affiliated to JNTUH & Approved by AICTE</h2>
        <h3>Accredited by NAAC with A++ Grade</h3>
    <p>Examination Cell - Invigilation Mail Automation Portal</p>
</div>

<div class="card">
    <h2>Upload Faculty CSV</h2>
    <form action="/faculty/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="file" required>
        <button type="submit">Upload & Preview</button>
    </form>
</div>

<div class="footer">
    © 2026 Vardhaman College of engineering | Examination Branch 
</div>

</body>
</html>
"""

# ================= UPLOAD + VALIDATE =================
@app.route("/faculty/upload", methods=["POST"])
def upload():
    file = request.files["file"]

    if not file.filename.endswith(".csv"):
        return "<h3 style='color:red;text-align:center;'>Only CSV files allowed!</h3>"

    df = pd.read_csv(file)

    # Validate required columns
    if not all(col in df.columns for col in REQUIRED_COLUMNS):
        return "<h3 style='color:red;text-align:center;'>CSV format incorrect! Required columns missing.</h3>"

    # Save validated file
    df.to_csv(VALIDATED_FILE, index=False)

    table_html = df.to_html(classes="data", index=False)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Preview Faculty Data</title>
        <style>
            body {{
                font-family: 'Segoe UI';
                background: linear-gradient(135deg,#1c92d2,#f2fcfe);
                text-align:center;
            }}
            table {{
                margin:auto;
                border-collapse: collapse;
                background:white;
            }}
            th, td {{
                padding:10px;
                border:1px solid #ddd;
            }}
            th {{
                background:#1c92d2;
                color:white;
            }}
            button {{
                margin:20px;
                padding:12px 30px;
                border:none;
                border-radius:8px;
                background:green;
                color:white;
                font-weight:bold;
                cursor:pointer;
            }}
        </style>
    </head>
    <body>
        <h1>Preview Faculty Invigilation List</h1>
        {table_html}
        <br>
        <a href="/faculty/send">
            <button>Send Emails to All Faculty</button>
        </a>
    </body>
    </html>
    """

# ================= SEND EMAILS =================
@app.route("/faculty/send")
def send_emails():
    df = pd.read_csv(VALIDATED_FILE)

    sender_email = "your_email@gmail.com"
    sender_password = "your_app_password"

    for index, row in df.iterrows():

        subject = "Invigilation Duty Intimation"

        body = f"""
Dear {row['faculty_name']},

This is to inform you that you are assigned invigilation duty for the examination.
.

Exam Date  : {row['exam_date']}
Exam Time  : {row['exam_time']}
Branch     : {row['branch']}

You are requested to report at the examination hall 30 minutes early to collect the booklets.

Your cooperation is highly appreciated.

Regards,
Examination Branch
Vardhaman College of Engineering
"""

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = row["email"]

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login("herekarnithish@gmail.com", "wuas vovf ikys nrre")
            server.send_message(msg)

    return """
<!DOCTYPE html>
<html>
<head>
<title>Mail Status</title>
<style>
body{
    font-family:'Segoe UI';
    background: linear-gradient(135deg,#e3f2fd,#bbdefb,#90caf9);
    text-align:center;
    padding-top:120px;
}
.card{
    width:400px;
    margin:auto;
    padding:40px;
    border-radius:20px;
    background: rgba(255,255,255,0.7);
    backdrop-filter: blur(15px);
    box-shadow:0 15px 35px rgba(0,0,0,0.2);
}
h2{
    color:#2e7d32;
}
button{
    margin-top:20px;
    padding:12px 25px;
    border:none;
    border-radius:10px;
    background: linear-gradient(135deg,#1976d2,#42a5f5);
    color:white;
    font-weight:bold;
    cursor:pointer;
}
button:hover{
    transform:scale(1.05);
}
</style>
</head>
<body>

<div class="card">
<h2>Emails Sent Successfully ✅</h2>
<a href="/">
<button>Go Back to Dashboard</button>
</a>
</div>

</body>
</html>
"""





# ------------------------------------------------------------
# RUN
# ------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)

    
# -------------------------
# PNG / PDF UTILS
# -------------------------

def draw_room_png(seats, assigns, students_map, out_path):
    if not seats: return
    max_r = max(s.r for s in seats)
    max_c = max(s.c for s in seats)
    
    fig, ax = plt.subplots(figsize=(max_c + 2, max_r + 2))
    ax.set_xlim(0, max_c + 1)
    ax.set_ylim(0, max_r + 1)
    ax.invert_yaxis()
    ax.axis("off") # Hide axes
    
    for s in seats:
        ax.add_patch(plt.Rectangle((s.c, s.r), 1, 1, fill=False))
        label = ""
        for roll, seat in assigns.items():
            if seat.seat_id == s.seat_id:
                st = students_map[roll]
                # Label format: Roll / Branch / Subject
                label = f"{roll}\n{st.branch}\n{st.subject}"
        ax.text(s.c + 0.1, s.r + 0.5, label, fontsize=6)
        
    plt.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

def png_to_pdf(png_path, pdf_path, title, subtitle):
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 750, title)
    c.setFont("Helvetica", 12)
    c.drawString(72, 730, subtitle)
    
    # Draw Image
    try:
        c.drawImage(png_path, 72, 200, width=450, height=450, preserveAspectRatio=True)
    except:
        pass
        
    c.save()

# -------------------------
# ROUTES: HOME & WIZARD
# -------------------------

@app.route("/")
def index():
    # Calculate stats for dashboard
    rooms_count = len(data_manager.get_rooms())
    subjects_count = len(data_manager.get_subjects())
    
    # Calculate total students from series
    # We can use get_all_generated_students() but that might be heavy if many.
    # Let's count quickly from series ranges.
    total_students = 0
    series = data_manager.get_student_series()
    for s in series:
        # Assuming format "PrefixNumber", we can try to parse or just call the utility
        # Using the utility is safer.
        students = data_manager.parse_series(s)
        total_students += len(students)

    
    active_exam = None
    if os.path.exists("active_exam.json"):
        with open("active_exam.json", "r") as f:
            active_exam = json.load(f)

    stats = {
        "rooms": rooms_count,
        "subjects": subjects_count,
        "students": total_students
    }
    return render_template("dashboard.html", stats=stats, active_exam=active_exam)

@app.route("/end_exam", methods=["POST"])
def end_exam():
    # Clear active exam data
    if os.path.exists("active_exam.json"):
        os.remove("active_exam.json")
    
    # Optionally clean static folder?
    # For now, just clearing the dashboard state.
    flash("Exam cleared successfully.", "success")
    return redirect(url_for("index"))



@app.route("/wizard/start")
def wizard_start():
    # Fetch all active branches per year to display availability in Step 1
    series = data_manager.get_student_series()
    availability = defaultdict(set)
    for s in series:
        availability[s["year"]].add(s["branch"])
    
    # Convert to sorted lists
    # {1: ["CIVIL", "CSE", "ECE", "MECH"], 2: ...}
    years_data = {}
    for y in range(1, 5):
        if y in availability:
            years_data[y] = sorted(list(availability[y]))
        else:
            years_data[y] = []
            
    return render_template("wizard_step1.html", years_data=years_data)




@app.route("/wizard/step2", methods=["POST"])
def wizard_step2():
    exam_name = request.form.get("exam_name")
    years = request.form.getlist("years") # ['1', '3'] etc
    years = [int(y) for y in years]
    
    # Get series for these years to find branches
    all_series = data_manager.get_student_series()
    active_branches_by_year = defaultdict(set)
    
    for s in all_series:
        if s["year"] in years:
            active_branches_by_year[s["year"]].add(s["branch"])
            
    # Convert sets to sorted lists
    branches_by_year = {y: sorted(list(b)) for y, b in active_branches_by_year.items()}
    
    all_subjects = data_manager.get_subjects()
    
    return render_template(
        "wizard_step2.html",
        exam_name=exam_name,
        selected_years=years,
        branches_by_year=branches_by_year,
        all_subjects=all_subjects
    )

@app.route("/wizard/step3", methods=["POST"])
def wizard_step3():
    exam_name = request.form.get("exam_name")
    selected_years_str = request.form.get("selected_years") # "1,3"
    
    # Parse Subject Map
    # Form data: "subject_1_CSE": "DBMS", "subject_3_ECE": "DLD"
    subject_map = {}
    
    for key, val in request.form.items():
        if key.startswith("subject_"):
            # key format: subject_YEAR_BRANCH
            parts = key.split("_")
            if len(parts) >= 3:
                year = int(parts[1])
                branch = parts[2]
                subject_map[key] = val
                
    # Calculate Total Students for Capacity Guidance
    total_students_count = 0
    all_series = data_manager.get_student_series()
    
    # Filter series matching the selected map
    # Logic: If (year, branch) is in subject_map, count matches
    # subject_map keys: subject_1_CSE
    
    active_pairs = set()
    for k in subject_map.keys():
        parts = k.split("_")
        y = int(parts[1])
        b = parts[2]
        active_pairs.add((y, b))
        
    for s in all_series:
        if (s["year"], s["branch"]) in active_pairs:
             # Fast count using range logic if available or parsing
             batch_list = data_manager.parse_series(s)
             total_students_count += len(batch_list)

    # Determine Efficiency Factor (1.0 for multi-branch, 0.5 for single-branch)
    unique_branches = set()
    for k in subject_map.keys():
        parts = k.split("_")
        unique_branches.add(parts[2])
    
    efficiency_factor = 0.5 if len(unique_branches) == 1 else 1.0

    all_rooms = data_manager.get_rooms()
    
    return render_template(
        "wizard_step3.html",
        exam_name=exam_name,
        selected_years=selected_years_str,
        subject_map_json=json.dumps(subject_map),
        all_rooms=all_rooms,
        total_students_count=total_students_count,
        efficiency_factor=efficiency_factor
    )

@app.route("/generate_v2", methods=["POST"])
def generate_v2():
    exam_name = request.form.get("exam_name")
    selected_years_str = request.form.get("selected_years", "")
    selected_years = [int(y) for y in selected_years_str.split(",") if y]
    
    subject_map_json = request.form.get("subject_map")
    subject_map_raw = json.loads(subject_map_json) # {"subject_1_CSE": "DBMS"}
    
    # Transform map to (Year, Branch) -> Subject
    # Actually just (Branch, Year) -> Subject mostly?
    # Let's map it: map[(year, branch)] = subject
    final_subject_map = {}
    for k, v in subject_map_raw.items():
        parts = k.split("_")
        y = int(parts[1])
        b = parts[2]
        final_subject_map[(y, b)] = v
        
    room_ids = request.form.getlist("room_ids")
    
    # 1. Fetch Students
    raw_students = data_manager.get_all_generated_students(year_filter=selected_years)
    
    # 2. Assign Subjects
    processed_students = []
    for s in raw_students:
        key = (s["year"], s["branch"])
        if key in final_subject_map:
            stu_obj = Student(s["roll"], s["branch"], s["year"], final_subject_map[key])
            processed_students.append(stu_obj)
            
    # 3. Fetch Rooms
    db_rooms = data_manager.get_rooms()
    selected_rooms_data = [r for r in db_rooms if r["id"] in room_ids]
    
    # --- V2.1: Capacity Validation ---
    total_seats = sum(r["rows"] * r["cols"] for r in selected_rooms_data)
    total_students = len(processed_students)
    
    if total_students > total_seats:
        flash(f"⚠️ Capacity Error: You have {total_students} students but only {total_seats} seats selected. Please select more rooms.", "error")
        # Redirect back to Step 3 (Select Rooms)
        # We need to re-pass variables to render Step 3. 
        # Easier to redirect to Wizard Start? Or just re-render template.
        # Since Step 3 depends on form data from Step 2, re-rendering `wizard_step3` needs that data.
        # Let's try to grab it from hidden input if possible, or robustly:
        # Re-render wizard_step3.html with context
        return render_template(
            "wizard_step3.html",
            exam_name=exam_name,
            selected_years=selected_years_str,
            subject_map_json=subject_map_json,
            all_rooms=db_rooms,
            error_message=f"Insufficient Capacity ({total_students} students > {total_seats} seats)"
        )
    # ---------------------------------
    
    # 4. Generate
    assigns, seats = generate_seating_v2(processed_students, selected_rooms_data)
    
    # 5. Output
    os.makedirs("static", exist_ok=True)
    students_map = {s.roll: s for s in processed_students}
    
    # Save CSV
    with open("static/assignments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["roll", "branch", "year", "subject", "room", "row", "col"])
        for roll, st in students_map.items():
            if roll in assigns:
                seat = assigns[roll]
                w.writerow([roll, st.branch, st.year, st.subject, seat.room, seat.r, seat.c])

    # PNGs/PDFs
    rooms_grouped = defaultdict(list)
    for s in seats:
        rooms_grouped[s.room].append(s)
        
    room_pngs = []
    
    # Save active exam file for Dashboard history
    active_exam_info = {
        "name": exam_name,
        "date": "2026-01-29", # Todo: dynamic date
        "students": total_students,
        "rooms": list(rooms_grouped.keys())
    }
    with open("active_exam.json", "w") as f:
        json.dump(active_exam_info, f)

    for room_name, r_seats in rooms_grouped.items():
        safe_name = room_name.replace(" ", "_")
        png_path = f"static/{safe_name}.png"
        pdf_path = f"static/{safe_name}.pdf"
        
        # New PDF generator
        pdf_generator.generate_room_pdf(
            pdf_path, 
            room_name, 
            exam_name, 
            r_seats, 
            assigns, 
            students_map
        )
        room_pngs.append(safe_name + ".pdf") # Keep track of files to zip

    # Create ZIP of all PDFs
    zip_path = "static/all_assignments.zip"
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for f in room_pngs:
            file_path = f"static/{f}"
            if os.path.exists(file_path):
                zipf.write(file_path, arcname=f)



    # Pass room names instead of pngs
    result = {
        "assigned": len(assigns),
        "total": len(processed_students),
        "rooms": list(rooms_grouped.keys()) # just names
    }
    
    return render_template("results.html", result=result)

@app.route("/download_zip")
def download_zip():
    return send_file("static/all_assignments.zip", as_attachment=True)



# -------------------------
# ROUTES: MANAGEMENT
# -------------------------

@app.route("/rooms", methods=["GET"])
def manage_rooms():
    return render_template("rooms.html", rooms=data_manager.get_rooms())

@app.route("/rooms/add", methods=["POST"])
def add_room():
    name = request.form.get("name")
    rows = request.form.get("rows")
    cols = request.form.get("cols")
    data_manager.add_room(name, rows, cols)
    return redirect(url_for("manage_rooms"))

@app.route("/rooms/delete/<id>", methods=["POST"])
def delete_room(id):
    data_manager.delete_room(id)
    return redirect(url_for("manage_rooms"))

@app.route("/subjects", methods=["GET"])
def manage_subjects():
    return render_template("subjects.html", subjects=data_manager.get_subjects())

@app.route("/subjects/add", methods=["POST"])
def add_subject():
    name = request.form.get("name")
    data_manager.add_subject(name)
    return redirect(url_for("manage_subjects"))

@app.route("/subjects/delete/<name>", methods=["POST"])
def delete_subject(name):
    data_manager.delete_subject(name)
    return redirect(url_for("manage_subjects"))

@app.route("/students", methods=["GET"])
def manage_students():
    return render_template("students.html", series=data_manager.get_student_series())

@app.route("/students/add", methods=["POST"])
def add_series():
    branch = request.form.get("branch")
    year = request.form.get("year")
    start = request.form.get("start")
    end = request.form.get("end")
    data_manager.add_student_series(branch, year, start, end)
    return redirect(url_for("manage_students"))

@app.route("/students/delete/<id>", methods=["POST"])
def delete_series(id):
    data_manager.delete_student_series(id)
    return redirect(url_for("manage_students"))

def validate_faculty_csv(file):
    required_fields = {
        "faculty_id",
        "faculty_name",
        "branch",
        "email",
        "exam_date",
        "exam_time"
    }

    reader = csv.DictReader(file)

    if not reader.fieldnames:
        return False, "CSV file is empty"

    if set(reader.fieldnames) != required_fields:
        return False, f"CSV header mismatch. Required columns: {required_fields}"

    rows = list(reader)

    if not rows:
        return False, "CSV has no data rows"

    for i, r in enumerate(rows, start=2):
        for field in required_fields:
            if not r.get(field):
                return False, f"Row {i}: Missing value for '{field}'"

    return True, rows

EMAIL_USER = "yourgmail@gmail.com"
EMAIL_PASS = "your_app_password"

def send_invigilation_email(to_email, faculty_name, branch, exam_date, time_slot):

    to_email = str(to_email).strip()

    # ❌ FINAL SAFETY CHECK
    if to_email == "" or to_email.lower() == "nan" or "@" not in to_email:
        return

    msg = EmailMessage()
    msg["Subject"] = f"Invigilation Duty – {exam_date}"
    msg["From"] = str(EMAIL_USER)
    msg["To"] = to_email   # ✅ now always string

    msg.set_content(f"""
Dear {faculty_name},

You are assigned invigilation duty.

Branch : {branch}
Date   : {exam_date}
Time   : {time_slot}

Please report 30 minutes early.

Regards,
Examination Branch
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

if __name__ == "__main__":
    app.run(debug=True)


