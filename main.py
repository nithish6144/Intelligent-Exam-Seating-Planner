# main.py - Dynamic Seating Prototype (greedy + swap, per-room PNG/PDF)
import sys, os, csv, random
from collections import defaultdict, namedtuple
import pandas as pd
import matplotlib
matplotlib.use("Agg")    
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Try OR-Tools CP fallback (optional)
try:
    from ortools.sat.python import cp_model
    ORTOOLS_AVAILABLE = True
except Exception:
    ORTOOLS_AVAILABLE = False

random.seed(1)
Student = namedtuple('Student', ['roll','branch','exam','special'])
Seat = namedtuple('Seat', ['seat_id','room','r','c','accessible','reserved'])

# Read students CSV
def read_students(path):
    df = pd.read_csv(path, comment='#', skip_blank_lines=True)
    # tolerate small header differences
    if 'roll_no' not in df.columns and 'roll' in df.columns:
        df = df.rename(columns={'roll':'roll_no'})
    if 'special_needs' not in df.columns and 'special' in df.columns:
        df = df.rename(columns={'special':'special_needs'})
    students = []
    for _,row in df.iterrows():
        roll = str(row.get('roll_no') or '').strip()
        branch = str(row.get('branch') or '').strip()
        exam = str(row.get('exam') or '').strip()
        special = row.get('special_needs',0)
        try:
            special = int(special)
        except:
            special = 1 if str(special).lower() in ('true','yes','y','1') else 0
        students.append(Student(roll, branch, exam, special))
    return students
# Replace the existing read_rooms function with this robust version
def read_rooms(path):
    df = pd.read_csv(path, comment='#', skip_blank_lines=True)
    rooms_seats = []
    for _,row in df.iterrows():
        room_id = str(row.get('room_id') or row.get('room') or '').strip()
        try:
            rows = int(row.get('rows') or 0)
        except:
            rows = 0
        try:
            cols = int(row.get('cols') or 0)
        except:
            cols = 0

        reserved_raw = str(row.get('reserved') or '').strip()
        accessible_raw = str(row.get('accessible') or '').strip()
        reserved = set()
        accessible = set()

        # Helper to parse tokens like "0-0;1-2" safely
        def parse_coord_list(raw):
            out = set()
            if not raw or raw.lower() in ('nan','none'):
                return out
            # split by semicolon and clean tokens
            tokens = [t.strip() for t in raw.split(';') if t is not None]
            for token in tokens:
                if token == '':
                    continue
                # ignore tokens that are not in expected 'int-int' format
                parts = [p.strip() for p in token.split('-') if p.strip()!='']
                if len(parts) != 2:
                    # skip malformed token
                    continue
                try:
                    r = int(parts[0]); c = int(parts[1])
                except:
                    continue
                out.add((r,c))
            return out

        reserved = parse_coord_list(reserved_raw)
        accessible = parse_coord_list(accessible_raw)

        for rpos in range(rows):
            for cpos in range(cols):
                sid = f"{room_id}-{rpos}-{cpos}"
                acc = 1 if (rpos,cpos) in accessible else 0
                res = 1 if (rpos,cpos) in reserved else 0
                rooms_seats.append(Seat(sid, room_id, rpos, cpos, acc, res))
    return rooms_seats

# Build adjacency (8-neighbour)
def build_adjacency(seats):
    by_room = defaultdict(list)
    for s in seats:
        by_room[s.room].append(s)
    adjacency = {s.seat_id:set() for s in seats}
    for room,seats_in_room in by_room.items():
        pos_map = {(s.r,s.c):s for s in seats_in_room}
        for s in seats_in_room:
            for dr in (-1,0,1):
                for dc in (-1,0,1):
                    if dr==0 and dc==0: continue
                    key = (s.r+dr, s.c+dc)
                    if key in pos_map:
                        adjacency[s.seat_id].add(pos_map[key].seat_id)
    return adjacency

# Hard check and soft-cost (minimize same-branch neighbors)
def hard_ok(student, seat, assign_map, seats_by_id, adjacency, students_map):
    if seat.reserved: return False
    if seat.seat_id in assign_map.values(): return False
    if student.special and not seat.accessible: return False
    # optional: avoid same-exam adjacency; currently skipped
    return True

def soft_cost(student, seat_id, assign_map, students_map, adjacency):
    cost = 0
    for neigh in adjacency.get(seat_id,()):
        for r,sid in assign_map.items():
            if sid == neigh and students_map[r].branch == student.branch:
                cost += 1
    return cost

# Greedy assignment across all seats
def greedy_assign(students, seats, adjacency, students_map):
    assign = {}
    seats_by_id = {s.seat_id:s for s in seats}
    ordered = sorted(students, key=lambda x: (not x.special,))
    for st in ordered:
        candidates = []
        for s in seats:
            if s.seat_id in assign.values(): continue
            if s.reserved: continue
            # check immediate adjacency for same-branch
            bad = False
            for neigh in adjacency.get(s.seat_id,()):
                for r,sid in assign.items():
                    if sid == neigh and students_map[r].branch == st.branch:
                        bad = True; break
                if bad: break
            if bad: continue
            candidates.append(s.seat_id)
        if not candidates:
            candidates = [s.seat_id for s in seats if s.seat_id not in assign.values() and not s.reserved]
        best = min(candidates, key=lambda seat_id: soft_cost(st, seat_id, assign, students_map, adjacency))
        assign[st.roll] = best
    return assign

# Swap-based improvement
def total_soft(assign_map, students_map, adjacency):
    tot = 0
    for r,seatid in assign_map.items():
        tot += soft_cost(students_map[r], seatid, assign_map, students_map, adjacency)
    return tot

def swap_improve(assign_map, students_map, seats_by_id, adjacency, iterations=3000):
    student_ids = list(assign_map.keys())
    best_cost = total_soft(assign_map, students_map, adjacency)
    for _ in range(iterations):
        if len(student_ids) < 2: break
        a,b = random.sample(student_ids,2)
        sa, sb = assign_map[a], assign_map[b]
        assign_map[a], assign_map[b] = sb, sa
        # validate no reserved and special needs respected
        if not (hard_ok(students_map[a], seats_by_id[assign_map[a]], assign_map, seats_by_id, adjacency, students_map) and
                hard_ok(students_map[b], seats_by_id[assign_map[b]], assign_map, seats_by_id, adjacency, students_map)):
            assign_map[a], assign_map[b] = sa, sb
            continue
        # ensure no same-branch adjacency anywhere (strict)
        violation = False
        for r, seatid in assign_map.items():
            for neigh in adjacency.get(seatid,()):
                for rr, sid2 in assign_map.items():
                    if sid2==neigh and students_map[rr].branch == students_map[r].branch:
                        violation = True; break
                if violation: break
            if violation: break
        if violation:
            assign_map[a], assign_map[b] = sa, sb
            continue
        new_cost = total_soft(assign_map, students_map, adjacency)
        if new_cost < best_cost:
            best_cost = new_cost
        else:
            assign_map[a], assign_map[b] = sa, sb
    return assign_map, best_cost

# Optional per-room CP fallback (requires ortools)
def solve_room_with_cp(students_in_room, seats_in_room, adjacency, time_limit_sec=5):
    if not ORTOOLS_AVAILABLE:
        return None
    model = cp_model.CpModel()
    n = len(students_in_room); m = len(seats_in_room)
    x = {}
    for i in range(n):
        for j in range(m):
            x[(i,j)] = model.NewBoolVar(f'x_{i}_{j}')
    for i in range(n):
        model.Add(sum(x[(i,j)] for j in range(m)) == 1)
    for j in range(m):
        model.Add(sum(x[(i,j)] for i in range(n)) <= 1)
    for i in range(n):
        for j in range(m):
            seat = seats_in_room[j]; st = students_in_room[i]
            if seat.reserved: model.Add(x[(i,j)] == 0)
            if st.special and not seat.accessible: model.Add(x[(i,j)] == 0)
    # adjacency forbid for same-branch
    for i in range(n):
        for u in range(i+1,n):
            if students_in_room[i].branch == students_in_room[u].branch:
                for j in range(m):
                    for k in range(m):
                        if seats_in_room[k].seat_id in adjacency.get(seats_in_room[j].seat_id,()):
                            model.Add(x[(i,j)] + x[(u,k)] <= 1)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_sec
    solver.parameters.num_search_workers = 8
    res = solver.Solve(model)
    if res == cp_model.OPTIMAL or res == cp_model.FEASIBLE:
        assign = {}
        for i in range(n):
            for j in range(m):
                if solver.Value(x[(i,j)]) == 1:
                    assign[students_in_room[i].roll] = seats_in_room[j].seat_id
        return assign
    return None

# Draw room to PNG
def draw_room(seats_in_room, assignment_map, students_map, out_png_path):
    max_r = max(s.r for s in seats_in_room); max_c = max(s.c for s in seats_in_room)
    rows = max_r+1; cols = max_c+1
    fig,ax = plt.subplots(figsize=(cols*1.0, rows*1.0))
    ax.set_xlim(0,cols); ax.set_ylim(0,rows); ax.invert_yaxis(); ax.axis('off')
    for s in seats_in_room:
        x = s.c; y = s.r
        rect = plt.Rectangle((x,y),1,1,fill=False)
        ax.add_patch(rect)
        # label
        label = ''
        for roll, sid in assignment_map.items():
            if sid == s.seat_id:
                label = f"{roll}\\n{students_map[roll].branch}"; break
        if s.reserved: label = 'RES'
        if s.accessible: ax.text(x+0.02, y+0.2, 'A', fontsize=8)
        ax.text(x+0.02, y+0.5, label, fontsize=8)
    plt.savefig(out_png_path, bbox_inches='tight'); plt.close(fig)

def png_to_pdf(png_path, pdf_path, title='Room Seating'):
    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.setFont('Helvetica', 12); c.drawString(72, 750, title)
    c.drawImage(png_path, 72, 200, width=450, height=450); c.save()

# Main workflow
def main(students_csv, rooms_csv, out_dir='output'):
    if not os.path.exists(out_dir): os.makedirs(out_dir)
    students = read_students(students_csv)
    seats = read_rooms(rooms_csv)
    adjacency = build_adjacency(seats)
    seats_by_room = defaultdict(list)
    for s in seats: seats_by_room[s.room].append(s)
    students_map = {s.roll:s for s in students}
    seats_by_id = {s.seat_id:s for s in seats}

    # Greedy assign
    print('Running greedy assignment...')
    assign = greedy_assign(students, seats, adjacency, students_map)
    print(f'Initially assigned: {len(assign)}/{len(students)}')
    remaining = [s for s in students if s.roll not in assign]
    for st in remaining:
        for seat in seats:
            if seat.seat_id in assign.values(): continue
            if hard_ok(st, seat, assign, seats_by_id, adjacency, students_map):
                assign[st.roll] = seat.seat_id; break
    print(f'After fill: {len(assign)}/{len(students)}')

    # Swap improve
    assign, cost = swap_improve(assign, students_map, seats_by_id, adjacency, iterations=5000)
    print(f'Soft-cost: {cost}')

    # Per-room CP fallback if violation
    room_assignments = defaultdict(dict)
    for roll, seatid in assign.items():
        room = seats_by_id[seatid].room
        room_assignments[room][roll] = seatid
    for room, mapping in room_assignments.items():
        seats_in_room = seats_by_room[room]
        violation = False
        for roll, seatid in mapping.items():
            for neigh in adjacency.get(seatid,()):
                for r2, sid2 in mapping.items():
                    if sid2 == neigh and students_map[r2].branch == students_map[roll].branch:
                        violation = True; break
                if violation: break
            if violation: break
        if violation:
            print(f'Violation in {room}, trying CP fallback...')
            students_in_room = [students_map[r] for r in mapping.keys()]
            cp_assign = solve_room_with_cp(students_in_room, seats_in_room, adjacency, time_limit_sec=3)
            if cp_assign:
                for roll, seatid in cp_assign.items(): assign[roll] = seatid
                print(f'CP solved {room}')
            else:
                print(f'CP failed or not available for {room}')

    # Write assignments.csv
    with open('assignments.csv','w',newline='',encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(['roll','branch','exam','seat_id','room','row','col','special'])
        for s in students:
            seatid = assign.get(s.roll,'UNASSIGNED')
            if seatid == 'UNASSIGNED':
                w.writerow([s.roll,s.branch,s.exam,seatid,'','','',s.special])
            else:
                st = seats_by_id[seatid]; w.writerow([s.roll,s.branch,s.exam,seatid,st.room,st.r,st.c,s.special])
    print('Wrote assignments.csv')

    # Write per-room PNG/PDF
    for room, seats_room in seats_by_room.items():
        out_png = os.path.join(out_dir, f'{room}.png')
        draw_room(seats_room, assign, students_map, out_png)
        out_pdf = os.path.join(out_dir, f'{room}.pdf')
        png_to_pdf(out_png, out_pdf, title=f'Room {room} Seating')
    print(f'Wrote per-room layouts to {out_dir}')

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python main.py students.csv rooms.csv')
    else:
        main(sys.argv[1], sys.argv[2])
