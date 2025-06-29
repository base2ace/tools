# tracker.py – logs app/site usage

import time, sqlite3, win32gui, win32process, psutil, re
from datetime import datetime
import json
from collections import defaultdict
from datetime import datetime

DB_NAME = "activity_log.db"

def create_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT,
            window_title TEXT,
            site TEXT,
            start_time TEXT,
            end_time TEXT,
            duration INTEGER,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_active_window():
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        p = psutil.Process(pid)
        return p.name(), win32gui.GetWindowText(hwnd)
    except:
        return None, None

def extract_site(title):
    if " - Google Chrome" in title:
        parts = title.replace(" - Google Chrome", "").rsplit(" - ", 1)
        return parts[-1].strip() if parts else ""
    m = re.search(r'https?://(www\.)?([^\s/]+)', title)
    return m.group(2) if m else ""

def save_session(app_name, title, start, end):
    dur = int((end - start).total_seconds())
    date = start.strftime("%Y-%m-%d")
    site = extract_site(title) if "chrome" in app_name.lower() else None

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO activity_log (app_name, window_title, site, start_time, end_time, duration, date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (app_name, title, site, start.isoformat(), end.isoformat(), dur, date))
    conn.commit()
    conn.close()

def activity_monitor():
    last_app, last_title = None, None
    start = datetime.now()
    create_db()
    while True:
        time.sleep(1)
        app, title = get_active_window()
        if (app, title) != (last_app, last_title):
            end = datetime.now()
            if last_app:
                save_session(last_app, last_title, start, end)
            start, last_app, last_title = end, app, title

def load_activity_data(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def summarize_activity(data, start, end, scope='all'):
    app_data = defaultdict(int)
    site_data = defaultdict(int)

    for entry in data:
        timestamp = datetime.fromisoformat(entry['timestamp'])
        if not (start <= timestamp <= end):
            continue

        app = entry['app']
        site = entry.get('site')
        duration = entry['duration']

        if scope in ('all', 'apps'):
            app_data[app] += duration
        if scope in ('all', 'sites') and site:
            site_data[site] += duration

    return app_data, site_data

def categorize(app, site):
    if app == 'chrome.exe':
        if 'youtube' in site:
            return 'Entertainment'
        if 'stackoverflow' in site or 'github' in site:
            return 'Development'
        if 'gmail' in site or 'mail' in site:
            return 'Communication'
        return 'Browsing'
    elif 'code' in app.lower():
        return 'Development'
    elif 'word' in app.lower() or 'excel' in app.lower():
        return 'Productivity'
    elif 'game' in app.lower():
        return 'Gaming'
    else:
        return 'Other'


if __name__ == "__main__":
    print("Starting tracker... Ctrl+C to stop")
    try:
        activity_monitor()
    except KeyboardInterrupt:
        print("Stopped")
