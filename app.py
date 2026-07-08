from flask import Flask, request, jsonify, render_template
from datetime import datetime, date, timedelta
import json
import os
import threading
import webview

app = Flask(__name__, static_folder="static")


def run_flask():
    app.run(
        host="127.0.0.1",
        port=5000
    )

DATA_FILE = 'tasks_data.json'

DEFAULT_DATA = {
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

def load_data():
    """Load all data from the JSON file.
    Handles: file missing, file empty, file corrupted (JSONDecodeError).
    Always returns a fully-populated dict with all expected keys.
    """
    data = {}

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                data = json.loads(content)
        except (json.JSONDecodeError, ValueError, IOError):
            # File is corrupted or unreadable — start fresh and overwrite
            data = {}

    # Merge defaults so missing keys never cause KeyErrors
    for key, default_val in DEFAULT_DATA.items():
        if key not in data:
            data[key] = default_val

    return data

def save_data(data):
    """Save all data atomically to prevent corruption on crash/interrupt."""
    tmp_file = DATA_FILE + '.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(tmp_file, DATA_FILE)  # atomic rename on all platforms

def add_xp(data, amount):
    """Centralized, balanced XP/leveling logic.
    100 XP is required per level, and XP always accumulates in whole,
    predictable increments so leveling never 'jumps' unexpectedly.
    """
    if amount <= 0:
        return data

    data["xp"] += amount
    # Handle any number of level-ups in one go (e.g. big XP grants)
    while data["xp"] >= 100:
        data["level"] += 1
        data["xp"] -= 100

    return data


# XP awarded per full minute of focused work. Kept small and realistic so a
# single minute of focus never causes an unrealistic level jump.
XP_PER_FOCUS_MINUTE = 2


def check_and_update_streak(data, is_new_completion=False):
    """Smart daily streak calculation"""
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

@app.route('/api/tasks/<int:task_id>/toggle', methods=['POST'])
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

                # Add XP on task completion (balanced: 10 XP per task, 100 XP per level)
                data = add_xp(data, 10)

                # Check achievements
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
    return jsonify({
        "success": True,
        "streak": data["streak"],
        "weekly_stats": data["weekly_stats"],
        "level": data["level"],
        "xp": data["xp"],
        "achievements": data["achievements"]
    })

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

    focus_delta = max(0, int(req.get("focus_minutes", 0) or 0))
    break_delta = max(0, int(req.get("break_minutes", 0) or 0))

    data["focus_minutes"] += focus_delta
    data["break_minutes"] += break_delta

    # Award balanced XP for focused minutes only (breaks don't earn XP).
    # e.g. 1 minute -> 2 XP, so reaching a level (100 XP) takes ~50 focus minutes.
    if focus_delta > 0:
        data = add_xp(data, focus_delta * XP_PER_FOCUS_MINUTE)

    # Check 1000 focus minutes achievement
    if data["focus_minutes"] >= 1000 and "1000_focus_minutes" not in data["achievements"]:
        data["achievements"].append("1000_focus_minutes")

    save_data(data)
    return jsonify({
        "success": True,
        "level": data["level"],
        "xp": data["xp"],
        "achievements": data["achievements"]
    })


@app.route('/api/profile/soft-reset', methods=['POST'])
def soft_reset_progress():
    """Soft-reset progress stats (streak, level, XP, weekly stats, achievements,
    focus/break minutes) while keeping the user's tasks and tracks intact.
    Used when a user switches their profile aesthetic and opts in to a fresh start.
    """
    data = load_data()
    data["streak"] = 0
    data["last_completion_date"] = ""
    data["weekly_stats"] = {"Sat": 0, "Sun": 0, "Mon": 0, "Tue": 0, "Wed": 0, "Thu": 0, "Fri": 0}
    data["focus_minutes"] = 0
    data["break_minutes"] = 0
    data["level"] = 1
    data["xp"] = 0
    data["achievements"] = []
    save_data(data)
    return jsonify({"success": True, "data": data}), 200


@app.route('/api/profile/keep-stats', methods=['POST'])
def keep_stats_progress():
    """No-op counterpart to soft-reset.

    Used when a user changes their profile aesthetic (gender/style) but
    explicitly opts to KEEP their current streak, level, XP, weekly stats,
    achievements and focus/break minutes. Nothing is mutated here — the
    endpoint simply echoes back the current, untouched state so the
    frontend can re-sync its UI after the style change without guessing.
    """
    data = load_data()
    return jsonify({"success": True, "data": data}), 200


if __name__ == '__main__':
     threading.Thread(
        target=run_flask
    ).start()

webview.create_window(
        "My App",
        "http://127.0.0.1:5000"
    )
app.run(host="0.0.0.0", port=5000)
webview.start()