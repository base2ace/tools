# debug_dump.py
import sqlite3

conn = sqlite3.connect("activity_log.db")
c = conn.cursor()
c.execute("SELECT id, date, app_name, window_title, duration FROM activity_log ORDER BY id DESC LIMIT 20")
for row in c.fetchall():
    print(row)
conn.close()
