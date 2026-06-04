from flask import Flask, request, jsonify, render_template
from datetime import datetime, date, timedelta
import json
import os

app = Flask(__name__)

# مسارات ملفات حفظ البيانات
DATA_FILE = 'tasks_data.json'

def load_data():
    """تحميل البيانات بالكامل من ملف الـ JSON"""
    if not os.path.exists(DATA_FILE):
        return {
            "tasks": [],
            "tracks": ["عام", "مذاكرة", "برمجة", "جيم"],
            "streak": 0,
            "last_completion_date": "",
            "weekly_stats": {"Sat": 0, "Sun": 0, "Mon": 0, "Tue": 0, "Wed": 0, "Thu": 0, "Fri": 0},
            "focus_minutes": 0,
            "break_minutes": 0,
            "level": 1,
            "xp": 0,
            "achievements": []
        }
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    """حفظ البيانات بالكامل"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def check_and_update_streak(data, is_new_completion=False):
    """ميكانيكية حساب الـ Streak الناري بشكل يومي ذكي"""
    today_str = str(date.today())
    yesterday_str = str(date.today() - timedelta(days=1))
    last_date = data.get("last_completion_date", "")

    if is_new_completion:
        if last_date == today_str:
            pass
        elif last_date == yesterday_str:
            data["streak"] += 1
            data["last_completion_date"] = today_str
        else:
            data["streak"] = 1
            data["last_completion_date"] = today_str
    else:
        if last_date != today_str and last_date != yesterday_str and last_date != "":
            data["streak"] = 0

    return data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/init', methods=['GET'])
def get_init_data():
    data = load_data()
    data = check_and_update_streak(data)
    save_data(data)
    return jsonify(data)

@app.route('/api/tasks', methods=['POST'])
def add_task():
    data = load_data()
    req = request.json
    new_task = {
        "id": int(datetime.now().timestamp() * 1000),
        "text": req.get("text"),
        "track": req.get("track", "عام"),
        "completed": False
    }
    data["tasks"].append(new_task)
    save_data(data)
    return jsonify(new_task), 201

@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST', 'PUT'])
def toggle_task(task_id):
    data = load_data()
    req = request.json
    completed = req.get("completed", False)
    
    for task in data["tasks"]:
        if task["id"] == task_id:
            if completed and not task["completed"]:
                task["completed"] = True
                data = check_and_update_streak(data, is_new_completion=True)
                day_name = datetime.now().strftime('%a')
                if day_name in data["weekly_stats"]:
                    data["weekly_stats"][day_name] += 1
                
                # إضافة XP عند إكمال المهمة
                data["xp"] += 10
                if data["xp"] >= 100:
                    data["level"] += 1
                    data["xp"] -= 100
                
                # فحص الإنجازات
                completed_count = len([t for t in data["tasks"] if t["completed"]])
                if completed_count == 1 and "first_task" not in data["achievements"]:
                    data["achievements"].append("first_task")
                if data["streak"] == 7 and "7_day_streak" not in data["achievements"]:
                    data["achievements"].append("7_day_streak")
                if completed_count == 100 and "100_tasks_done" not in data["achievements"]:
                    data["achievements"].append("100_tasks_done")
            else:
                task["completed"] = completed
            break
            
    save_data(data)
    return jsonify({"success": True, "streak": data["streak"], "weekly_stats": data["weekly_stats"], "level": data["level"], "xp": data["xp"], "achievements": data["achievements"]})

@app.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    data = load_data()
    data["tasks"] = [t for t in data["tasks"] if t['id'] != task_id]
    save_data(data)
    return jsonify({"success": True}), 200

@app.route('/api/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    data = load_data()
    req = request.json
    
    for task in data["tasks"]:
        if task["id"] == task_id:
            task["text"] = req.get("text", task["text"])
            task["track"] = req.get("track", task["track"])
            save_data(data)
            return jsonify(task), 200
    
    return jsonify({"error": "Task not found"}), 404

@app.route('/api/tracks', methods=['POST'])
def add_track():
    data = load_data()
    new_track = request.json.get("track_name")
    if new_track and new_track not in data["tracks"]:
        data["tracks"].append(new_track)
        save_data(data)
        return jsonify({"success": True, "tracks": data["tracks"]}), 201
    return jsonify({"success": False}), 400

@app.route('/api/pomodoro/save', methods=['POST'])
def save_pomodoro():
    data = load_data()
    req = request.json
    
    data["focus_minutes"] += req.get("focus_minutes", 0)
    data["break_minutes"] += req.get("break_minutes", 0)
    
    # فحص الإنجاز 1000 دقيقة تركيز
    if data["focus_minutes"] >= 1000 and "1000_focus_minutes" not in data["achievements"]:
        data["achievements"].append("1000_focus_minutes")
    
    save_data(data)
    return jsonify({"success": True, "level": data["level"], "xp": data["xp"], "achievements": data["achievements"]})

if __name__ == '__main__':
    app.run(port=5000, debug=True)