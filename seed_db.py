
import data_manager

print("Seeding database...")

# Clear existing series to avoid duplicates if re-run (simple approach)
# Ideally delete_all, but for now we just append. To avoid duplicates, user can delete db.json manually or we rely on unique IDs.
# Let's simple check if "db.json" exists and delete it to start fresh? 
# Using os.remove is risky if we lose rooms. 
# Let's just add if not exist logic not implemented in data_manager for keys.
# Actually, the user wants a full refresh. 
# I'll overwrite the db file entirely in this script?
# No, data_manager.save_db handles writing.
# Let's mimic a fresh start by creating a fresh dict.

DB = {
    "rooms": [],
    "subjects": [],
    "student_series": []
}
data_manager.save_db(DB)

# 1. Add Rooms
data_manager.add_room("Hall A (Ground Floor)", 10, 6)
data_manager.add_room("Lab 1 (First Floor)", 6, 6)
data_manager.add_room("Drawing Hall", 15, 10)
data_manager.add_room("Main Auditorium", 20, 15)

# 2. Add Subjects (Common engineering subjects)
subjects = [
    "Maths I", "Physics", "Chemistry", "C Programming",       # Year 1
    "Data Structures", "DLD", "Python", "Mechanics",          # Year 2
    "DBMS", "Operating Systems", "Computer Networks", "TOC",  # Year 3
    "AI", "ML", "Cloud Computing", "Cyber Security"           # Year 4
]
for s in subjects:
    data_manager.add_subject(s)

# 3. Add Student Series (Batches)
# We need CSE, ECE, MECH, CIVIL for Years 1, 2, 3, 4

branches = ["CSE", "ECE", "MECH", "CIVIL"]
years = [1, 2, 3, 4]

# Simplified roll number generation logic
# Y1: 24..., Y2: 23..., Y3: 22..., Y4: 21...
year_codes = {1: "24", 2: "23", 3: "22", 4: "21"}
branch_codes = {"CSE": "05", "ECE": "04", "MECH": "03", "CIVIL": "01"}

for y in years:
    y_code = year_codes[y]
    for br in branches:
        b_code = branch_codes[br]
        # Create a batch of ~60 students
        start = f"{y_code}881A{b_code}01"
        end = f"{y_code}881A{b_code}60"
        
        data_manager.add_student_series(br, y, start, end)
        print(f"Added {br} Year {y}: {start} - {end}")

print("Database seeded successfully with FULL data!")
