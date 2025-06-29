import sqlite3
import datetime
import json

DB_NAME = "activity_log.db"
REPORT_FILE = "activity_report.html"

def fetch_data_for_day(date_str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        SELECT app_name, site, SUM(duration)
        FROM activity_log
        WHERE date = ?
        GROUP BY app_name, site
    ''', (date_str,))
    rows = c.fetchall()
    conn.close()
    return rows

def generate_html(data, date_str):
    app_data = {}
    site_data = {}

    for app, site, duration in data:
        key = site if site else app
        app_data[key] = app_data.get(key, 0) + duration

        if app == "chrome.exe" and site:
            site_data[site] = site_data.get(site, 0) + duration

    # Prepare JSON for JS
    app_labels = json.dumps(list(app_data.keys()))
    app_values = json.dumps([round(v / 60, 2) for v in app_data.values()])
    site_labels = json.dumps(list(site_data.keys()))
    site_values = json.dumps([round(v / 60, 2) for v in site_data.values()])

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Usage Report - {date_str}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; cursor: pointer; }}
    </style>
</head>
<body>

<h2>Usage Report for {date_str}</h2>

<table id="usageTable">
    <thead>
        <tr>
            <th onclick="sortTable(0)">Application / Site</th>
            <th onclick="sortTable(1)">Duration (min:sec)</th>
        </tr>
    </thead>
    <tbody>
"""
    for key, seconds in sorted(app_data.items(), key=lambda x: -x[1]):
        mins = seconds // 60
        secs = seconds % 60
        html += f"<tr><td>{key}</td><td>{mins}:{secs:02}</td></tr>\n"

    html += f"""
    </tbody>
</table>

<h3>Application Usage</h3>
<canvas id="appChart" style="max-width: 800px; max-height: 800px;"></canvas>

<h3>Chrome Site Usage</h3>
<canvas id="siteChart" style="max-width: 800px; max-height: 800px;"></canvas>

<script>
function sortTable(n) {{
    var table = document.getElementById("usageTable");
    var rows = Array.from(table.rows).slice(1);
    var asc = table.getAttribute("data-sort-dir") !== "asc";
    rows.sort((a, b) => {{
        const x = a.cells[n].textContent.toLowerCase();
        const y = b.cells[n].textContent.toLowerCase();
        return asc ? x.localeCompare(y) : y.localeCompare(x);
    }});
    rows.forEach(row => table.appendChild(row));
    table.setAttribute("data-sort-dir", asc ? "asc" : "desc");
}}

const appChart = new Chart(document.getElementById('appChart'), {{
    type: 'bar',
    data: {{
        labels: {app_labels},
        datasets: [{{
            label: 'Usage Duration (minutes)',
            data: {app_values},
            backgroundColor: 'rgba(54, 162, 235, 0.7)'
        }}]
    }},
    options: {{
        responsive: true,
        plugins: {{
            legend: {{ display: false }}
        }}
    }}
}});

const siteChart = new Chart(document.getElementById('siteChart'), {{
    type: 'pie',
    data: {{
        labels: {site_labels},
        datasets: [{{
            label: 'Chrome Site Usage',
            data: {site_values},
            backgroundColor: [
                'rgba(255, 99, 132, 0.7)',
                'rgba(255, 206, 86, 0.7)',
                'rgba(75, 192, 192, 0.7)',
                'rgba(153, 102, 255, 0.7)',
                'rgba(255, 159, 64, 0.7)',
                'rgba(54, 162, 235, 0.7)',
                'rgba(100, 100, 255, 0.7)',
                'rgba(255, 100, 255, 0.7)'
            ]
        }}]
    }},
    options: {{
        responsive: true
    }}
}});
</script>

</body>
</html>
"""
    return html

def main():
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    data = fetch_data_for_day(date_str)
    html = generate_html(data, date_str)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ HTML report generated: {REPORT_FILE}")

if __name__ == "__main__":
    main()
