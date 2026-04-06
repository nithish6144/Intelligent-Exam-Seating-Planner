# ------------------------------------------------------------
# PDF Generator — ReportLab Utility
# ------------------------------------------------------------

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_room_pdf(filename, room_name, exam_name, seats, assigns, students_map):
    """
    Generates a PDF with:
    1. Room Header
    2. Seating Grid (Visual)
    """
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter),
                            rightMargin=50, leftMargin=50,
                            topMargin=50, bottomMargin=50)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=1, fontSize=24, spaceAfter=20)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Heading2'], alignment=1, fontSize=16, spaceAfter=40, textColor=colors.grey)
    
    elements.append(Paragraph(f"Seating Arrangement: {room_name}", title_style))
    elements.append(Paragraph(f"Exam: {exam_name}", subtitle_style))
    
    # -------------------------
    # Visual Grid
    # -------------------------
    # Determine dimensions
    if not seats:
        elements.append(Paragraph("No seats configured.", styles['Normal']))
        doc.build(elements)
        return

    max_r = max(s.r for s in seats)
    max_c = max(s.c for s in seats)
    rows = max_r + 1
    cols = max_c + 1
    
    # Create Matrix
    # row 0 is front? In our logic r=0 is front.
    # We want to display visually, usually Front at Top or Bottom?
    # Logic: r=0 is front. Let's display r=0 at the top of the table.
    
    grid_data = []
    
    # Header row (Cols 1, 2, 3...)
    # header = [""] + [f"Col {c+1}" for c in range(cols)]
    # grid_data.append(header)
    
    for r in range(rows):
        row_cells = []
        for c in range(cols):
            # Find student at r,c
            # Identify seat ID first
            # We need to look up efficienty.
            # But seats list doesn't have consistent ordering necessarily.
            # let's map it
            pass
            
    # Build Map
    seat_map_by_rc = {} # (r,c) -> Student
    for roll, seat_obj in assigns.items():
        if seat_obj.room == room_name: # Wait, seat_obj.room stores ID/Name
            # Currently our room.name IS the ID in V2 logic.
             if seat_obj.room == room_name: # Verified
                 stu = students_map[roll]
                 seat_map_by_rc[(seat_obj.r, seat_obj.c)] = stu

    # Construct Table Data
    # List of Lists
    
    # Logic: r=0 (Front) is usually Row 1 in PDF table.
    for r in range(rows):
        row_display = []
        for c in range(cols):
            if (r, c) in seat_map_by_rc:
                stu = seat_map_by_rc[(r, c)]
                # Cell Content
                cell_text = f"<b>{stu.roll}</b><br/>{stu.branch}<br/>{stu.subject}"
                # Create Paragraph for wrapping
                p = Paragraph(cell_text, styles['Normal'])
                row_display.append(p)
            else:
                row_display.append("Empty")
        grid_data.append(row_display)
        
    # Create Table
    # Auto calculate col width?
    # A4 Landscape width ~ 11 inch. Margins 1 inch. ~10 inch usable.
    # If 6 cols, ~1.5 inch per col.
    col_width = (10.0 / cols) * inch
    t = Table(grid_data, colWidths=[col_width]*cols)
    
    # Style
    style_cmds = [
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('PADDING', (0,0), (-1,-1), 12),
    ]
    
    # Add alternating colors if desirable, or specific branch colors?
    # Keeping it clean for now.
    
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    
    doc.build(elements)

# ------------------------------------------------------------
# Developed by: devai.co.in
# ------------------------------------------------------------
