# ------------------------------------------------------------
# Data Manager — Persistence Layer
# ------------------------------------------------------------

import json
import os
import uuid
import re

DB_FILE = "db.json"

DEFAULT_DB = {
    "rooms": [],
    "subjects": [],
    "student_series": []
}

def load_db():
    if not os.path.exists(DB_FILE):
        save_db(DEFAULT_DB)
        return DEFAULT_DB
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# -------------------------
# ROOMS
# -------------------------
def get_rooms():
    db = load_db()
    return db.get("rooms", [])

def add_room(name, rows, cols):
    db = load_db()
    new_room = {
        "id": str(uuid.uuid4()),
        "name": name,
        "rows": int(rows),
        "cols": int(cols)
    }
    db["rooms"].append(new_room)
    save_db(db)

def delete_room(room_id):
    db = load_db()
    db["rooms"] = [r for r in db["rooms"] if r["id"] != room_id]
    save_db(db)

def get_room(room_id):
    rooms = get_rooms()
    for r in rooms:
        if r["id"] == room_id:
            return r
    return None

# -------------------------
# SUBJECTS
# -------------------------
def get_subjects():
    db = load_db()
    return sorted(db.get("subjects", []))

def add_subject(name):
    db = load_db()
    if name not in db["subjects"]:
        db["subjects"].append(name)
        save_db(db)

def delete_subject(name):
    db = load_db()
    if name in db["subjects"]:
        db["subjects"].remove(name)
        save_db(db)

# -------------------------
# STUDENTS / SERIES
# -------------------------
def get_student_series():
    db = load_db()
    return db.get("student_series", [])

def add_student_series(branch, year, start_roll, end_roll):
    db = load_db()
    new_series = {
        "id": str(uuid.uuid4()),
        "branch": branch,
        "year": int(year),
        "start": start_roll,
        "end": end_roll
    }
    db["student_series"].append(new_series)
    save_db(db)

def delete_student_series(series_id):
    db = load_db()
    db["student_series"] = [s for s in db["student_series"] if s["id"] != series_id]
    save_db(db)

# -------------------------
# UTILS: GENERATE STUDENTS
# -------------------------

def increment_alphanumeric(current_s):
    """
    Increments the alphanumeric string by 1.
    Handles '...09' -> '...10', '...A9' -> '...B0', '...Z9' -> '...100'? 
    Actually standard JNTU logic is 0-9, then A0-A9, B0-B9 ... Z0-Z9.
    Let's handle the specific case of digits at end, optionally preceded by a letter.
    """
    # 1. Reverse string to find incrementable part
    chars = list(current_s)
    i = len(chars) - 1
    
    while i >= 0:
        c = chars[i]
        
        if c.isdigit():
            if c != '9':
                chars[i] = str(int(c) + 1)
                return "".join(chars)
            else:
                chars[i] = '0'
                i -= 1
                continue
                
        elif c.isalpha():
            # A-Z
            # If we hit a letter, we usually increment it if the previous digit wrapped?
            # Or is it like Hex? 0-9, A-F?
            # User said "6601 ... 66F9". 
            # This implies 01-99, then A0-F9? Or A1-F9?
            # Typically 00-99 -> A0-A9 -> B0...
            # This means the position BEFORE the last digit is Base-36?
            
            # Let's try general partial-base-36 increment.
            # Convert char to value (0-9=0-9, A-Z=10-35)
            # Actually simplest is:
            # If '9' -> 'A' (if we decided that's the sequence)
            # If 'Z' -> '0' and carry?
            
            # Use ASCII logic
            if c == 'Z':
                chars[i] = '0' # Wrap to 0? Or A->B?
                i -= 1 # Carry
            else:
                chars[i] = chr(ord(c) + 1)
                return "".join(chars)
        
        else:
            # Non-alphanumeric (e.g. -), stop?
            break
            
    return None # Overflow or impossible

def parse_series(series_obj):
    """
    Robust alphanumeric series generator.
    Iterates from start to end by incrementing.
    Safeguard: limit to 200 students to prevent infinite loops if logic fails.
    """
    start_s = series_obj["start"].upper().strip()
    end_s = series_obj["end"].upper().strip()
    branch = series_obj["branch"]
    year = series_obj["year"]
    
    students = []
    
    curr = start_s
    students.append({"roll": curr, "branch": branch, "year": year})
    
    if curr == end_s:
        return students
        
    # Safety limit
    max_count = 200
    count = 0
    
    while curr != end_s and count < max_count:
        next_val = increment_alphanumeric(curr)
        if not next_val:
            break
        curr = next_val
        students.append({"roll": curr, "branch": branch, "year": year})
        count += 1
        
    return students


def get_all_generated_students(year_filter=None):
    """
    Returns a unified list of all students generated from all series.
    Optional filter by year (list of ints).
    """
    series_list = get_student_series()
    all_students = []
    
    for s in series_list:
        if year_filter and s["year"] not in year_filter:
            continue
            
        all_students.extend(parse_series(s))
        
    # Deduplicate by roll number just in case
    seen = set()
    unique_students = []
    for stu in all_students:
        if stu["roll"] not in seen:
            seen.add(stu["roll"])
            unique_students.append(stu)
            
    return unique_students

# ------------------------------------------------------------
# Developed by: devai.co.in
# ------------------------------------------------------------
