# ------------------------------------------------------------
# app.py — Final Version (UNLIMITED BRANCH PAIR PATTERN + PER-BRANCH EXAMS)
# ------------------------------------------------------------

import os, csv
from collections import defaultdict
from flask import Flask, request, render_template_string, send_file, flash, redirect, url_for
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)
app.secret_key = "dev-secret-key"


# -------------------------
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


# -------------------------
# HTML – Step 1 (Enter Students)
# -------------------------

STEP1_HTML = """
<h2>Step 1: Enter Students (ROLL,BRANCH)</h2>

<form method="post">

  <textarea name="students_text" rows="10" cols="80" 
  placeholder="CSE01,CSE
ECE01,ECE
ME01,ME
IT01,IT"></textarea>
  <br><br>

<h3>Select Rooms for Seating</h3>
<p>Default room size: <b>6 × 4</b></p>

<input type="checkbox" name="room_1" checked> Room 1<br>
<input type="checkbox" name="room_2"> Room 2<br>
<input type="checkbox" name="room_3"> Room 3<br>
<input type="checkbox" name="room_4"> Room 4<br>
<input type="checkbox" name="room_5"> Room 5<br>

<input type="hidden" name="rows" value="6">
<input type="hidden" name="cols" value="4">


  <button type="submit">Next → Select Exams</button>

</form>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul style='color:red'>
      {% for m in messages %}
        <li>{{m}}</li>
      {% endfor %}
    </ul>
  {% endif %}
{% endwith %}
"""


# ------------------------------------------------------------
# STEP 2 — Exam selection per branch
# ------------------------------------------------------------

EXAM_OPTIONS = ["DS", "DBMS", "OS", "CN", "AI", "ML", "DAA", "COA", "DLD", "TOC"]

STEP2_HTML = """
<h2>Step 2: Select Exam for Each Branch</h2>

<form method="post" action="/generate">

  {% for br in branches %}
    <label>{{br}} Exam:</label>
    <select name="exam_{{br}}">
      {% for ex in exams %}
        <option value="{{ex}}">{{ex}}</option>
      {% endfor %}
    </select>
    <br><br>
  {% endfor %}

  <!-- store original students text + room config -->
  <input type="hidden" name="students_raw" value="{{students_raw}}">
  <input type="hidden" name="num_rooms" value="{{num_rooms}}">
  <input type="hidden" name="rows" value="{{rows}}">
  <input type="hidden" name="cols" value="{{cols}}">
  <input type="hidden" name="selected_rooms" value="{{ selected_rooms }}">


  <button type="submit">Generate Seating</button>

</form>
"""

# -------------------------
# HTML – Final Results Page
# -------------------------

INDEX_HTML = """
<!doctype html>
<title>Dynamic Seating System</title>
<h2>Seating Generated Successfully</h2>

{% if result %}
  <p>Assigned: {{result.assigned}} / {{result.total}}</p>
  <a href="{{ url_for('download_assignments') }}">Download assignments.csv</a>

  {% for f in result.room_pngs %}
    <h3>{{f}}</h3>
    <img src="{{ url_for('static', filename=f) }}" width="400"><br>
    <a href="{{ url_for('static', filename=f.replace('.png','.pdf')) }}">Download PDF</a><br><br>
  {% endfor %}

{% else %}
  <p>No data found.</p>
{% endif %}

<br><a href="/">Back to Home</a>
"""



# ------------------------------------------------------------
# Utility: Parse students
# ------------------------------------------------------------

def parse_students(txt):
    students = []
    years_found = set()

    for line in txt.splitlines():
        parts = [p.strip() for p in line.split(",")]

        if len(parts) == 2:
            # Format: ROLL,BRANCH  → year unknown for now
            roll, branch = parts
            students.append(Student(roll, branch, None))

        elif len(parts) >= 3:
            # Format: ROLL,BRANCH,YEAR
            roll, branch, year = parts[0], parts[1], int(parts[2])
            students.append(Student(roll, branch, year))
            years_found.add(year)

    return students




# ------------------------------------------------------------
# Group students by branch
# ------------------------------------------------------------

def group_students(students):
    groups = defaultdict(list)
    for s in students:
        groups[s.branch].append(s)
    for br in groups:
        groups[br].sort(key=lambda x: x.roll)
    return groups


# ------------------------------------------------------------
# Unlimited Branch Pairing
# ------------------------------------------------------------

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


# ------------------------------------------------------------
# MAIN SEATING LOGIC — unchanged
# ------------------------------------------------------------

def generate_seating(groups, exams_for_branch, num_rooms, rows, cols):
    # detect if multiple years exist
    all_years = {s.year for br in groups for s in groups[br] if s.year is not None}
    multi_year = False

    sorted_branches = sorted(groups.keys(), key=lambda b: len(groups[b]), reverse=True)

    branch_pairs = generate_branch_pairs(sorted_branches)
    num_pairs = len(branch_pairs)

    next_index = {br: 0 for br in sorted_branches}
    assigns = {}
    seats = []
    seat_map = {}   # (room_id, r, c) → Student

    for room_num in range(1, num_rooms + 1):
        room_id = f"R{room_num}"

        for c in range(cols):
            pair_index = c % num_pairs
            br1, br2 = branch_pairs[pair_index]

            for r in range(rows):

                branch = br1 if (r % 2 == 0) else br2
                if branch is None:
                    branch = br1

                seat_id = f"{room_id}-{r}-{c}"
                seat_obj = Seat(seat_id, room_id, r, c)
                seats.append(seat_obj)

                if next_index[branch] < len(groups[branch]):
                    stu = groups[branch][next_index[branch]]
                    stu.subject = exams_for_branch[branch]
                    can_place = True

                    if c > 0:
                        left_key = (room_id, r, c-1)
                        if (
                            multi_year
                            and left_key in seat_map
                            and seat_map[left_key].year is not None
                            and stu.year is not None
                            and seat_map[left_key].year == stu.year
                        ):
                            can_place = False

    # check FRONT seat
                    if r > 0:
                        front_key = (room_id, r-1, c)
                        if (
                            multi_year
                            and front_key in seat_map
                            and seat_map[front_key].year is not None
                            and stu.year is not None
                            and seat_map[front_key].year == stu.year
                        ):
                            can_place = False

                    if can_place:
                        assigns[stu.roll] = seat_obj
                        seat_map[(room_id, r, c)] = stu
                        next_index[branch] += 1

    return assigns, seats


# ------------------------------------------------------------
# PNG / PDF / CSV
# ------------------------------------------------------------

def draw_room_png(seats, assigns, students_map, out_path):
    if not seats:
        return

    max_r = max(s.r for s in seats)
    max_c = max(s.c for s in seats)

    fig, ax = plt.subplots(figsize=(max_c + 2, max_r + 2))
    ax.set_xlim(0, max_c + 1)
    ax.set_ylim(0, max_r + 1)
    ax.invert_yaxis()
    ax.axis("off")

    for s in seats:
        ax.add_patch(plt.Rectangle((s.c, s.r), 1, 1, fill=False))
        label = ""
        for roll, seat in assigns.items():
            if seat.seat_id == s.seat_id:
                st = students_map[roll]
                label = f"{roll}\n{st.branch}\n{st.subject}"
        ax.text(s.c + 0.05, s.r + 0.45, label, fontsize=8)

    plt.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def png_to_pdf(png_path, pdf_path, title):
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.drawString(72, 750, title)
    c.drawImage(png_path, 72, 200, width=450, height=450)
    c.save()


def write_assignments_csv(assigns, students_map, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["roll", "branch", "subject", "room", "row", "col"])
        for roll, st in students_map.items():
            if roll in assigns:
                seat = assigns[roll]
                w.writerow([roll, st.branch, st.subject, seat.room, seat.r, seat.c])


# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def step1():
    if request.method == "GET":
        return render_template_string(STEP1_HTML)

    students_raw = request.form.get("students_text", "").strip()
    students = parse_students(students_raw)

    if not students:
        flash("Enter students first.")
        return render_template_string(STEP1_HTML)

    branches = sorted({s.branch for s in students})

    return render_template_string(
        STEP2_HTML,
        branches=branches,
        exams=EXAM_OPTIONS,
        students_raw=students_raw,
        num_rooms=request.form.get("num_rooms"),
        rows=request.form.get("rows"),
        cols=request.form.get("cols"),
    )


@app.route("/generate", methods=["POST"])
def generate():
    students_raw = request.form.get("students_raw", "")
    students = parse_students(students_raw)

    # Extract exam choices for each branch
    branches = sorted({s.branch for s in students})
    exams_for_branch = {br: request.form.get(f"exam_{br}") for br in branches}

    selected_rooms = request.form.get("selected_rooms", "")
    selected_rooms = selected_rooms.strip("[]").replace("'", "").split(", ")

    if selected_rooms == [''] or not selected_rooms:
        selected_rooms = []

    num_rooms = len(selected_rooms)
    selected_rooms = request.form.get("selected_rooms", "")
    selected_rooms = selected_rooms.strip("[]").replace("'", "").split(", ")

    if selected_rooms == [''] or not selected_rooms:
        selected_rooms = ["R1"]   # fallback room
    num_rooms = len(selected_rooms)
    rows = int(request.form.get("rows"))
    cols = int(request.form.get("cols"))

    # Group and assign
    groups = group_students(students)
    assigns, seats = generate_seating(groups, exams_for_branch, num_rooms, rows, cols)

    students_map = {s.roll: s for s in students}

    os.makedirs("static", exist_ok=True)

    # Save CSV
    write_assignments_csv(assigns, students_map, "static/assignments.csv")

    # Generate PNG/PDF for each room
    rooms = defaultdict(list)
    for s in seats:
        rooms[s.room].append(s)

    room_pngs = []
    for room, room_seats in rooms.items():

        png_path = f"static/{room}.png"
        pdf_path = f"static/{room}.pdf"

        draw_room_png(room_seats, assigns, students_map, png_path)
        png_to_pdf(png_path, pdf_path, f"Room {room}")

        room_pngs.append(f"{room}.png")

    # Prepare final result dictionary for INDEX_HTML
    result = {
        "assigned": len(assigns),
        "total": len(students),
        "room_pngs": room_pngs
    }

    # Render INDEX_HTML again WITH THE RESULT
    return render_template_string(
        INDEX_HTML,
        result=result
    )



@app.route("/download_assignments")
def download_assignments():
    return send_file("static/assignments.csv", as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
