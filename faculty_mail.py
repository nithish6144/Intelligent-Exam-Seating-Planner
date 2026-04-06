from flask import Flask, request, redirect, url_for, flash
import pandas as pd
import smtplib
from email.mime.text import MIMEText
import os

app = Flask(__name__)
app.secret_key = "examcellsecret"

REQUIRED_COLUMNS = [
    'faculty_id',
    'faculty_name',
    'branch',
    'email',
    'exam_date',
    'exam_time'
]

VALIDATED_FILE = "validated.csv"

# ================= HOME PAGE =================
@app.route("/")
def home():
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
    <form action="/upload" method="post" enctype="multipart/form-data">
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
@app.route("/upload", methods=["POST"])
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
        <a href="/send">
            <button>Send Emails to All Faculty</button>
        </a>
    </body>
    </html>
    """

# ================= SEND EMAILS =================
@app.route("/send")
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

if __name__ == "__main__":
    app.run(debug=True)

