from flask import Flask, request, redirect, render_template, url_for
from datetime import datetime, timedelta
from db import (
    get_stream, get_all_streams, update_stream, delete_stream,
    log_access, get_access_log
)
from fetcher import fetch_info
from config import UPDATE_INTERVAL_HOURS

app = Flask(__name__)
last_update = None

@app.route("/stream")
def stream():
    name = request.args.get("name")
    if not name:
        print("[ERROR] /stream called without name param")
        return "Missing stream name", 400

    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    cf_ip = request.headers.get('CF-Connecting-IP', ip)
    url = get_stream(name)

    if url:
        print(f"[STREAM] Redirecting {ip} (CF: {cf_ip}) to {url}")
        log_access(name, ip, cf_ip)
        return redirect(url)
    else:
        print(f"[ERROR] Stream not found for name={name}")
        return "Stream not found", 404

@app.route("/dashboard")
def dashboard():
    global last_update
    streams = get_all_streams()
    now = datetime.utcnow()
    next_update = (last_update + timedelta(hours=UPDATE_INTERVAL_HOURS)) if last_update else None
    return render_template("dashboard.html", streams=streams, last_update=last_update, next_update=next_update)

@app.route("/dashboard/refresh", methods=["POST"])
def refresh():
    global last_update
    streams = get_all_streams()
    for name, stream in streams.items():
        info = fetch_info(stream["url"])
        if info:
            update_stream(name, stream["url"], info["m3u8"], info["channel"])
    last_update = datetime.utcnow()
    return redirect(url_for("dashboard"))

@app.route("/dashboard/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form.get("name")
        url = request.form.get("url")
        info = fetch_info(url)
        if info:
            update_stream(name, url, info["m3u8"], info["channel"])
        return redirect(url_for("dashboard"))
    return render_template("add.html")

@app.route("/dashboard/delete", methods=["POST"])
def delete():
    name = request.form.get("name")
    delete_stream(name)
    return redirect(url_for("dashboard"))

@app.route("/logs")
def logs():
    raw_logs = get_access_log()
    grouped = {}

    for log in raw_logs:
        channel = log.get("channel", "Unknown")
        ip = log.get("ip", "Unknown")
        cf_ip = log.get("cf_ip", ip)
        timestamp = log.get("timestamp")

        if channel not in grouped:
            grouped[channel] = {}

        if ip not in grouped[channel]:
            grouped[channel][ip] = []

        grouped[channel][ip].append({
            "timestamp": timestamp,
            "cf_ip": cf_ip
        })

    return render_template("logs.html", grouped_logs=grouped)
