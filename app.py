import logging
import os
from flask import Flask, request, redirect, render_template, url_for, Response, flash
from datetime import datetime, timedelta
from db import (
    get_stream, streams_table, update_stream, delete_stream,
    log_access, get_access_log,
    read_channels_file, write_channels_file, load_db
)
from fetcher import fetch_info
from config import UPDATE_INTERVAL_HOURS
from repair_coordinator import RepairCoordinator
from runtime_health import check_readiness
from scheduler import (
    refresh_from_channels_txt,
    scheduler_running,
    start_scheduler,
)
from stream_service import repair_stream, save_fetch_result

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "youtube-redirector-dashboard")
repair_coordinator = RepairCoordinator(repair_stream, cooldown_seconds=300)

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
        log_access(name, ip, outcome="redirected")
        # Removed noisy INFO log line here
        return redirect(url)

    if name not in read_channels_file() and name not in streams_table():
        logger.warning(f"Unknown stream {name} requested by client {ip}")
        return "Stream not found", 404

    outcome = repair_coordinator.request(name, timeout=30)
    if outcome == "redirected":
        url = get_stream(name)
        if url:
            log_access(name, ip, outcome="redirected")
            return redirect(url)
        outcome = "repair_failed"

    log_access(name, ip, outcome=outcome)
    logger.warning(f"Stream {name} unavailable for client {ip}: {outcome}")
    return Response(
        "Stream temporarily unavailable",
        status=503,
        headers={"Retry-After": "30"},
    )

@app.route("/dashboard")
def dashboard():
    streams = streams_table()
    db = load_db()
    lu = db.get("last_update")
    nu = None
    lu_fmt = None
    nu_fmt = None

    if lu:
        lu_dt = datetime.fromisoformat(lu)
        nu_dt = lu_dt + timedelta(hours=UPDATE_INTERVAL_HOURS)
        lu_fmt = lu_dt.strftime("%H:%M:%S on %d-%m-%Y")
        nu_fmt = nu_dt.strftime("%H:%M:%S on %d-%m-%Y")

    logger.info("Dashboard accessed")
    return render_template(
        "dashboard.html",
        streams=streams,
        last_update=lu_fmt,
        next_update=nu_fmt
    )

@app.route("/dashboard/refresh", methods=["POST"])
def refresh():
    logger.info("Manual dashboard refresh triggered")
    if refresh_from_channels_txt(source="manual"):
        flash("Refresh completed.", "success")
    else:
        flash("Refresh already running.", "warning")
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
            save_fetch_result(name, url, info)
            logger.info(f"Added new stream {name}")
        else:
            update_stream(name, url, None, None, status="failed", last_error="Initial fetch failed")
            logger.warning(f"Failed to add stream {name}")

        channels = read_channels_file()
        channels[name] = url
        write_channels_file(channels)

        return redirect(url_for("dashboard"))
    return render_template("add.html")


@app.route("/dashboard/check-live", methods=["POST"])
def check_live():
    name = request.form.get("name", "").strip()
    if name:
        channels = read_channels_file()
        url = channels.get(name)
        if not url:
            stream_data = streams_table().get(name, {})
            url = stream_data.get("url")
        if url:
            if repair_stream(name):
                flash(f"{name} live stream updated.", "success")
            else:
                flash(f"No live stream found for {name}.", "warning")
    return redirect(url_for("dashboard"))


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
        ts = log.get("timestamp")

        # Format timestamp if present
        ts_fmt = None
        if ts:
            try:
                ts_dt = datetime.fromisoformat(ts)
                ts_fmt = ts_dt.strftime("%H:%M:%S on %d-%m-%Y")
            except Exception:
                ts_fmt = ts  # fallback to raw string

        if channel not in grouped:
            grouped[channel] = {}

        if ip not in grouped[channel]:
            grouped[channel][ip] = []

        grouped[channel][ip].append({"timestamp": ts_fmt})

    logger.info("Logs accessed")
    return render_template("logs.html", grouped_logs=grouped)

@app.route("/download_channels")
def download_channels():
    channels = read_channels_file()
    content = "\n".join([f"{name},{url}" for name, url in channels.items()])
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment;filename=channels.txt"}
    )

@app.route("/health")
def health():
    healthy = check_readiness(
        db_loader=load_db,
        data_dir=os.getenv("DATA_DIR", "."),
        scheduler_running=scheduler_running,
    )
    return ("OK", 200) if healthy else ("UNHEALTHY", 503)
