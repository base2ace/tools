# gen_report.py

import argparse
from datetime import datetime, timedelta
import sqlite3
from collections import defaultdict
import os

DB_NAME = "activity_log.db"
HTML_REPORT = "activity_report.html"

def load_data_from_db(start_time, end_time):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT app_name, site, duration, start_time FROM activity_log 
        WHERE start_time BETWEEN ? AND ?
    ''', (start_time.isoformat(), end_time.isoformat()))
    rows = c.fetchall()
    conn.close()
    return rows

def summarize(rows, scope='both'):
    app_data = defaultdict(int)
    site_data = defaultdict(int)

    for app, site, duration, _ in rows:
        if scope in ('apps', 'both'):
            app_data[app] += duration
        if scope in ('sites', 'both') and site:
            site_data[site] += duration

    return app_data, site_data

def categorize(app, site):
    site = site.lower() if site else ''
    app = app.lower() if app else ''

    if app == 'chrome.exe':
        if 'youtube' in site:
            return 'Entertainment'
        elif any(x in site for x in ['stackoverflow', 'github', 'gitlab']):
            return 'Development'
        elif 'mail' in site or 'gmail' in site:
            return 'Communication'
        elif 'deepseek' in site or 'chat.openai' in site:
            return 'Research'
        elif 'report' in site:
            return 'Documentation'
        return 'Browsing'
    elif 'code' in app:
        return 'Development'
    elif 'pycharm' in app:
        return 'Development'
    elif 'word' in app or 'excel' in app:
        return 'Productivity'
    elif 'game' in app:
        return 'Gaming'
    elif 'explorer' in app or 'framehost' in app:
        return 'System'
    return 'Other'


def generate_html(app_data, site_data):
    html = """<html><head><meta charset='UTF-8'><title>Activity Report</title></head>
    <body><h1>Activity Report</h1><table border='1'>
    <tr><th>Application/Site</th><th>Time Spent</th><th>Category</th></tr>
    """

    combined_data = {}

    # Only keep valid site entries (must look like real domain names)
    filtered_sites = {k: v for k, v in site_data.items() if '.' in k}

    # Merge with app data
    combined_data.update(app_data)
    combined_data.update(filtered_sites)

    for key, seconds in sorted(combined_data.items(), key=lambda x: -x[1]):
        mins = seconds // 60
        secs = seconds % 60
        category = categorize('chrome.exe', key) if key in filtered_sites else categorize(key, "")
        html += f"<tr><td>{key}</td><td>{mins}:{secs:02}</td><td>{category}</td></tr>\n"

    html += "</table></body></html>"
    return html


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=str, help="Start datetime (YYYY-MM-DD)", default=None)
    parser.add_argument('--end', type=str, help="End datetime (YYYY-MM-DD)", default=None)
    parser.add_argument('--scope', choices=['apps', 'sites', 'both'], default='both')
    parser.add_argument('--output', type=str, default=HTML_REPORT)
    args = parser.parse_args()

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    start_time = datetime.strptime(args.start, "%Y-%m-%d") if args.start else today
    end_time = datetime.strptime(args.end, "%Y-%m-%d") + timedelta(days=1) if args.end else today + timedelta(days=1)

    rows = load_data_from_db(start_time, end_time)
    app_data, site_data = summarize(rows, scope=args.scope)

    html = generate_html(app_data, site_data)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Report generated: {os.path.abspath(args.output)}")

if __name__ == "__main__":
    main()
