# tracker.py

import time
import sqlite3
import win32gui
import win32process
import psutil
from datetime import datetime
import os
import re

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
        process = psutil.Process(pid)
        app_name = process.name()
        title = win32gui.GetWindowText(hwnd)
        return app_name, title
    except Exception:
        return None, None


def extract_site(title):
    if " - Google Chrome" in title:
        parts = title.replace(" - Google Chrome", "").rsplit(" - ", 1)
        return parts[-1].strip() if parts else ""
    match = re.search(r'https?://(www\.)?([^\s/]+)', title)
    return match.group(2) if match else ""


def save_session(app_name, title, start_time, end_time):
    duration = int((end_time - start_time).total_seconds())
    date = start_time.strftime("%Y-%m-%d")
    site = extract_site(title) if "chrome" in app_name.lower() else None

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # print(f"Saving session: {app_name}, {title}, {duration} sec")
    c.execute('''
        INSERT INTO activity_log (app_name, window_title, site, start_time, end_time, duration, date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (app_name, title, site, start_time.isoformat(), end_time.isoformat(), duration, date))
    conn.commit()
    conn.close()


def activity_monitor():
    last_app, last_title = None, None
    start_time = datetime.now()

    while True:
        time.sleep(1)
        app_name, title = get_active_window()
        # print(f"Detected: {app_name}, Title: {title}")
        if (app_name, title) != (last_app, last_title):
            end_time = datetime.now()
            if last_app:
                save_session(last_app, last_title, start_time, end_time)
            start_time = end_time
            last_app, last_title = app_name, title


if __name__ == "__main__":
    print("Starting background tracker. Running... (Press Ctrl+C to stop)")
    create_db()
    try:
        activity_monitor()
    except KeyboardInterrupt:
        print("\nTracking stopped.")
