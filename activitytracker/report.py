# report.py

import sqlite3
import argparse
from datetime import datetime, timedelta

DB_NAME = "activity_log.db"

def query_by_period(period="day", value=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if period == "day":
        c.execute('''
            SELECT app_name, site, SUM(duration)
            FROM activity_log
            WHERE date = ?
            GROUP BY app_name, site
        ''', (value,))

    elif period == "month":
        c.execute('''
            SELECT app_name, site, SUM(duration)
            FROM activity_log
            WHERE date LIKE ?
            GROUP BY app_name, site
        ''', (f"{value}%",))

    elif period == "week":
        year, week = value.split("-W")
        week = int(week)
        monday = datetime.strptime(f'{year}-W{week}-1', "%Y-W%W-%w")
        week_dates = [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        placeholders = ','.join('?' for _ in week_dates)

        c.execute(f'''
            SELECT app_name, site, SUM(duration)
            FROM activity_log
            WHERE date IN ({placeholders})
            GROUP BY app_name, site
        ''', week_dates)
    else:
        print("Invalid period. Use 'day', 'week', or 'month'.")
        return

    rows = c.fetchall()
    conn.close()

    print(f"\n=== Usage Report for {period.upper()} {value} ===\n")
    if not rows:
        print("No usage data available.")
        return

    for app, site, duration in rows:
        label = site if site else app
        print(f"{label:40} - {duration // 60} min {duration % 60} sec")

def main():
    parser = argparse.ArgumentParser(description="Query activity usage logs.")
    parser.add_argument("period", choices=["day", "week", "month"], help="Report period")
    parser.add_argument("value", help="Date (YYYY-MM-DD), week (YYYY-W##), or month (YYYY-MM)")
    args = parser.parse_args()
    query_by_period(args.period, args.value)

if __name__ == "__main__":
    main()
