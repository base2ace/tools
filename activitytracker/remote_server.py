from flask import Flask, jsonify, send_file
import subprocess
import os

app = Flask(__name__)
REPORT_FILE = "activity_report.html"

@app.route("/ping")
def ping():
    return jsonify(status="ok", message="Tracker is running")

@app.route("/generate_report")
def generate_report():
    try:
        subprocess.run(["python", "generate_html_report.py"], check=True)
        return jsonify(status="ok", report=REPORT_FILE)
    except Exception as e:
        return jsonify(status="error", error=str(e))

@app.route("/report")
def report():
    if os.path.exists(REPORT_FILE):
        return send_file(REPORT_FILE)
    return jsonify(status="error", message="No report available")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
