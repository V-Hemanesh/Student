from flask import Flask, render_template, jsonify, request
import json
import os

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
    
    # Recalculate stats naively for demonstration
    total_gpa = sum(float(s["gpa"]) for s in data["students"])
    total_att = sum(float(s["attendance"]) for s in data["students"])
    count = len(data["students"])
    
    if count > 0:
        data["average_gpa"] = round(total_gpa / count, 2)
        data["overall_attendance"] = round(total_att / count, 1)
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
        
    # Recalculate stats
    total_gpa = sum(float(s["gpa"]) for s in data["students"])
    total_att = sum(float(s["attendance"]) for s in data["students"])
    count = len(data["students"])
    
    if count > 0:
        data["average_gpa"] = round(total_gpa / count, 2)
        data["overall_attendance"] = round(total_att / count, 1)
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

@app.route('/api/performance-trend')
def get_performance_trend():
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    students = data.get("students", [])
    status_counts = {"Excellent": 0, "Good": 0, "Average": 0, "Needs Improvement": 0}
    for s in students:
        status = s.get("status", "Needs Improvement")
        if status in status_counts:
            status_counts[status] += 1
            
    return jsonify({
        "labels": list(status_counts.keys()),
        "datasets": [{
            "label": "Number of Students",
            "data": list(status_counts.values())
        }]
    })

@app.route('/api/attendance-trend')
def get_attendance_trend():
    data = load_data()
    if "error" in data:
        return jsonify(data), 404
        
    students = data.get("students", [])
    # Sort by attendance descending and take top 7
    sorted_students = sorted(students, key=lambda x: float(x.get("attendance", 0)), reverse=True)[:7]
    
    labels = [s.get("name").split()[0] for s in sorted_students] # First name for label
    attendance_data = [s.get("attendance") for s in sorted_students]
    
    return jsonify({
        "labels": labels,
        "datasets": [{
            "label": "Attendance %",
            "data": attendance_data
        }]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
