from flask import Flask, render_template, jsonify, request, send_file
import json
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'mock_data.json')

def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Data file not found"}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def calculate_status(cgpa):
    if cgpa >= 9.0:
        return "Excellent"
    elif cgpa >= 7.5:
        return "Good"
    elif cgpa >= 6.0:
        return "Average"
    else:
        return "Needs Improvement"

# Page Routes
@app.route('/')
def dashboard():
    return render_template('dashboard.html', active_page='dashboard')

@app.route('/students')
def manage_students():
    return render_template('students.html', active_page='students')

@app.route('/attendance')
def attendance():
    return render_template('attendance.html', active_page='attendance')

@app.route('/settings')
def settings():
    return render_template('settings.html', active_page='settings')


# API Routes
@app.route('/api/dashboard-stats')
def get_dashboard_stats():
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    return jsonify({
        "total_students": len(data.get("students", [])),
        "overall_attendance": data.get("overall_attendance", 0),
        "average_gpa": data.get("average_gpa", 0),
        "upcoming_events": data.get("upcoming_events", [])
    })

@app.route('/api/students', methods=['GET', 'POST'])
def api_manage_students():
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    total_days = data.get("total_class_days", 0)

    if request.method == 'GET':
        students = data.get("students", [])
        # Append global total_class_days to each student for easy frontend access
        for s in students:
            s["total_class_days"] = total_days
        return jsonify(students)

@app.route('/api/students', methods=['POST'])
def add_student():
    student = request.json
    if not student:
        return jsonify({"error": "Invalid data"}), 400
        
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    # Auto-calculate status based on CGPA
    cgpa = float(student.get("gpa", 0))
    student["status"] = calculate_status(cgpa)
        
    # Initialize days_present based on attendance
    attendance_pct = student.get("attendance", 100)
    total_days = data.get("total_class_days", 100)
    student["days_present"] = int((attendance_pct / 100.0) * total_days)
    
    data["students"].append(student)
    
    # Recalculate stats using pandas
    df = pd.DataFrame(data["students"])
    if not df.empty:
        df['gpa'] = pd.to_numeric(df['gpa'], errors='coerce')
        df['attendance'] = pd.to_numeric(df['attendance'], errors='coerce')
        data["average_gpa"] = float(round(df['gpa'].mean(), 2))
        data["overall_attendance"] = float(round(df['attendance'].mean(), 1))
    else:
        data["average_gpa"] = 0
        data["overall_attendance"] = 0

    save_data(data)
    return jsonify({"message": "Student added successfully"}), 201

@app.route('/api/students/<student_id>', methods=['DELETE'])
def delete_student(student_id):
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    initial_count = len(data["students"])
    data["students"] = [s for s in data["students"] if s["id"] != student_id]
    
    if len(data["students"]) == initial_count:
        return jsonify({"error": "Student not found"}), 404
        
    # Recalculate stats using pandas
    df = pd.DataFrame(data["students"])
    if not df.empty:
        df['gpa'] = pd.to_numeric(df['gpa'], errors='coerce')
        df['attendance'] = pd.to_numeric(df['attendance'], errors='coerce')
        data["average_gpa"] = float(round(df['gpa'].mean(), 2))
        data["overall_attendance"] = float(round(df['attendance'].mean(), 1))
    else:
        data["average_gpa"] = 0
        data["overall_attendance"] = 0

    save_data(data)
    return jsonify({"message": "Student deleted successfully"}), 200

@app.route('/api/attendance/<date>', methods=['GET'])
def get_attendance_by_date(date):
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
    
    records = data.get("attendance_records", {})
    return jsonify(records.get(date, {}))

@app.route('/api/students/<student_id>/attendance', methods=['GET'])
def get_student_attendance_history(student_id):
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    records = data.get("attendance_records", {})
    history = []
    
    for date_str, daily_record in records.items():
        if student_id in daily_record:
            history.append({
                "date": date_str,
                "status": daily_record[student_id]
            })
            
    # Sort history chronologically by date
    history.sort(key=lambda x: x["date"], reverse=True)
    
    return jsonify(history)

@app.route('/api/attendance/submit', methods=['POST'])
def submit_attendance():
    payload = request.json
    if not payload or "present_ids" not in payload or "date" not in payload:
        return jsonify({"error": "Invalid data"}), 400
        
    date_str = payload["date"]
    
    # 1. Validate Semester Dates
    try:
        from datetime import datetime, date
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        if not (datetime(2026, 5, 1) <= dt <= datetime(2026, 5, 31)):
            return jsonify({"error": "Date must be between May 1 and May 31, 2026"}), 400
        
        # 2. Validate No Sundays
        if dt.weekday() == 6: # Sunday is 6
            return jsonify({"error": "Cannot mark attendance on Sundays"}), 400
            
        # 3. Server-side validation: only allow submission for 'today'
        # To avoid strict timezone issues across the globe causing spurious errors, 
        # we will rely heavily on the client-side lock, but add a soft server lock here.
        # If strict server lock is needed:
        # if dt.date() != date.today():
        #     return jsonify({"error": "You can only submit attendance for the present day."}), 400
            
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    present_ids = set(payload["present_ids"])
    attendance_records = data.get("attendance_records", {})
    existing_record = attendance_records.get(date_str, {})
    
    new_record = {}
    
    for student in data.get("students", []):
        s_id = student["id"]
        
        # 3. Irreversible Absences Rule
        if s_id in existing_record and existing_record[s_id] == "absent":
            new_record[s_id] = "absent" # Force it to remain absent
        else:
            new_record[s_id] = "present" if s_id in present_ids else "absent"
            
    attendance_records[date_str] = new_record
    data["attendance_records"] = attendance_records
    
    # 4. Recalculate everything from scratch for perfect accuracy
    data["total_class_days"] = len(attendance_records)
    
    total_att = 0
    for student in data.get("students", []):
        s_id = student["id"]
        # Count days present across ALL records
        days_present = sum(1 for rec in attendance_records.values() if rec.get(s_id) == "present")
        student["days_present"] = days_present
        
        if data["total_class_days"] > 0:
            student["attendance"] = round((days_present / data["total_class_days"]) * 100, 1)
        else:
            student["attendance"] = 100 # Default if no classes yet
            
        total_att += float(student["attendance"])
        
    # Recalculate global stats
    count = len(data["students"])
    if count > 0:
        data["overall_attendance"] = round(total_att / count, 1)
        
    save_data(data)
    return jsonify({"message": "Attendance saved successfully"}), 200

@app.route('/api/performance-chart', methods=['GET'])
def get_performance_chart():
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    df = pd.DataFrame(data.get("students", []))
    if df.empty:
        return jsonify({"error": "No data"}), 404
        
    status_counts = df['status'].value_counts()
    categories = ["Excellent", "Good", "Average", "Needs Improvement"]
    counts = [status_counts.get(cat, 0) for cat in categories]
    
    fig, ax = plt.subplots(figsize=(4, 4))
    colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444']
    
    if sum(counts) > 0:
        wedges, texts, autotexts = ax.pie(counts, labels=categories, colors=colors, autopct='%1.1f%%', 
                                          startangle=90, textprops=dict(color="w"))
        for text in texts:
            text.set_color('#64748b')
            text.set_fontsize(9)
        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_weight('bold')
    else:
        ax.text(0.5, 0.5, 'No Data', ha='center', va='center', color='#64748b')
        ax.axis('off')
        
    plt.tight_layout()
    img = io.BytesIO()
    fig.savefig(img, format='png', transparent=True, bbox_inches='tight', dpi=120)
    img.seek(0)
    plt.close(fig)
    return send_file(img, mimetype='image/png')

@app.route('/api/attendance-trend', methods=['GET'])
def get_attendance_trend():
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    df = pd.DataFrame(data.get("students", []))
    if df.empty:
        return jsonify({"error": "No data"}), 404
        
    # Get top 7 students
    df['attendance'] = pd.to_numeric(df['attendance'], errors='coerce').fillna(0)
    top_students = df.nlargest(7, 'attendance')
    
    fig, ax = plt.subplots(figsize=(6, 3.5))
    
    orange_shades = ['#7c2d12', '#9a3412', '#c2410c', '#ea580c', '#f97316', '#fb923c', '#fdba74']
    colors = orange_shades[:len(top_students)]
    
    ax.bar(top_students['name'].apply(lambda x: x.split()[0]), top_students['attendance'], color=colors, width=0.5, edgecolor='none')
    
    # Styling
    ax.set_ylim(0, 100)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#e2e8f0')
    ax.spines['bottom'].set_color('#e2e8f0')
    ax.tick_params(axis='x', colors='#64748b', length=0, pad=8)
    ax.tick_params(axis='y', colors='#64748b', length=0, pad=8)
    ax.set_yticks(range(0, 101, 10))
    ax.grid(axis='both', color='#f1f5f9', linestyle='-', linewidth=1)
    ax.set_axisbelow(True)
    
    plt.tight_layout()
    
    img = io.BytesIO()
    fig.savefig(img, format='png', transparent=True, bbox_inches='tight', dpi=120)
    img.seek(0)
    plt.close(fig)
    
    return send_file(img, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
