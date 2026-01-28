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
    seat_map = {} # Global seat map (room_id, r, c) -> Student

    # 2. Iterate through rooms
    for room_data in room_list:
        room_id = room_data["name"] # Use Name as ID for readability
        rows = int(room_data["rows"])
        cols = int(room_data["cols"])
        
        for c in range(cols):
            # Rotate pair index based on column to mix things up
            pair_index = c % num_pairs
            br1, br2 = branch_pairs[pair_index]

            for r in range(rows):
                # Checkerboard logic
                branch = br1 if (r % 2 == 0) else br2
                if branch is None:
                    branch = br1
                
                seat_uid = f"{room_id}-{r}-{c}"
                seat_obj = Seat(seat_uid, room_id, r, c)
                seats.append(seat_obj)
                
                if next_index[branch] < len(groups[branch]):
                    stu = groups[branch][next_index[branch]]
                    
                    # Check adjacency (Left and Front)
                    can_place = True
                    
                    # Check Left
                    if c > 0:
                        left_key = (room_id, r, c-1)
                        if left_key in seat_map:
                            if seat_map[left_key].subject == stu.subject:
                                can_place = False
                    
                    # Check Front
                    if r > 0:
                        front_key = (room_id, r-1, c)
                        if front_key in seat_map:
                            if seat_map[front_key].subject == stu.subject:
                                can_place = False
                                
                    if can_place:
                        assigns[stu.roll] = seat_obj
                        seat_map[(room_id, r, c)] = stu
                        next_index[branch] += 1
                        
    return assigns, seats

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

@app.route("/download_assignments")
def download_assignments():
    return send_file("static/assignments.csv", as_attachment=True)


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

if __name__ == "__main__":
    app.run(debug=True)

# ------------------------------------------------------------
# Developed by: devai.co.in
# ------------------------------------------------------------
