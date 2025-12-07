import logging
from flask import Flask, request, redirect, render_template, url_for
from datetime import datetime, timedelta
from db import (
    get_stream, streams_table, update_stream, delete_stream,
    log_access, get_access_log,
    read_channels_file, write_channels_file, load_db, save_db
)
from fetcher import fetch_info
from config import UPDATE_INTERVAL_HOURS
from scheduler import start_scheduler

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

app = Flask(__name__)

logger.info("Starting scheduler and reading channels.txt at launch...")
start_scheduler()

@app.route("/stream")
def stream():
    name = request.args.get("name")
    if not name:
        return "Missing stream name", 400

    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    url = get_stream(name)

    if url:
        log_access(name, ip)
        logger.info(f"Redirecting client {ip} to stream {name}")
        return redirect(url)
    logger.warning(f"Stream {name} not found for client {ip}")
    return "Stream not found", 404

@app.route("/dashboard")
def dashboard():
    streams = streams_table()
    db = load_db()
    lu = db.get("last_update")
    nu = None
    lu_dt = None
    if lu:
        lu_dt = datetime.fromisoformat(lu)
        nu = lu_dt + timedelta(hours=UPDATE_INTERVAL_HOURS)
    logger.info("Dashboard accessed")
    return render_template("dashboard.html", streams=streams,
                           last_update=lu_dt, next_update=nu)

@app.route("/dashboard/refresh", methods=["POST"])
def refresh():
    logger.info("Manual dashboard refresh triggered")
    channels = read_channels_file()
    for name, url in channels.items():
        info = fetch_info(url)
        if info:
            update_stream(name, url, info.get("m3u8"), info.get("channel"))
            logger.info(f"Updated {name} via manual refresh")
        else:
            update_stream(name, url, None, None)
            logger.warning(f"Failed to update {name} via manual refresh")

    db = load_db()
    db["last_update"] = datetime.utcnow().isoformat()
    save_db(db)

    return redirect(url_for("dashboard"))

@app.route("/dashboard/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        url = request.form.get("url", "").strip()
        if not name or not url:
            return redirect(url_for("dashboard"))

        info = fetch_info(url)
        if info:
            update_stream(name, url, info.get("m3u8"), info.get("channel"))
            logger.info(f"Added new stream {name}")
        else:
            update_stream(name, url, None, None)
            logger.warning(f"Failed to add stream {name}")

        channels = read_channels_file()
        channels[name] = url
        write_channels_file(channels)

        return redirect(url_for("dashboard"))
    return render_template("add.html")

@app.route("/dashboard/delete", methods=["POST"])
def delete():
    name = request.form.get("name", "").strip()
    if name:
        delete_stream(name)
        channels = read_channels_file()
        if name in channels:
            del channels[name]
            write_channels_file(channels)
        logger.info(f"Deleted stream {name}")
    return redirect(url_for("dashboard"))

@app.route("/logs")
def logs():
    raw_logs = get_access_log()
    grouped = {}

    for log in raw_logs:
        channel = log.get("channel", "Unknown")
        ip = log.get("ip", "Unknown")
        timestamp = log.get("timestamp")

        if channel not in grouped:
            grouped[channel] = {}

        if ip not in grouped[channel]:
            grouped[channel][ip] = []

        grouped[channel][ip].append({"timestamp": timestamp})

    logger.info("Logs accessed")
    return render_template("logs.html", grouped_logs=grouped)
