import logging
from flask import Flask, request, redirect, render_template, url_for, Response
from datetime import datetime, timedelta
from db import (
    get_stream, streams_table, update_stream, delete_stream,
    log_access, get_access_log,
    read_channels_file, write_channels_file, load_db, set_last_update
)
from fetcher import fetch_info, repair_live_info
from config import UPDATE_INTERVAL_HOURS
from scheduler import start_scheduler

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

app = Flask(__name__)

logger.info("Starting scheduler and reading channels.txt at launch...")
start_scheduler()


def save_fetch_result(name, original_url, info, update_channels=False):
    new_url = info.get("source_url") or info.get("resolved_live_url") or original_url
    update_stream(
        name,
        new_url,
        info.get("m3u8"),
        info.get("channel") or name,
        status=info.get("status"),
        last_error=info.get("last_error"),
        resolved_live_url=info.get("resolved_live_url"),
        channel_url=info.get("channel_url"),
        channel_id=info.get("channel_id"),
    )
    if update_channels and new_url != original_url:
        channels = read_channels_file()
        channels[name] = new_url
        write_channels_file(channels)
    return new_url


@app.route("/stream")
def stream():
    name = request.args.get("name")
    if not name:
        return "Missing stream name", 400

    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    url = get_stream(name)

    if url:
        log_access(name, ip)
        # Removed noisy INFO log line here
        return redirect(url)
    logger.warning(f"Stream {name} not found for client {ip}")
    return "Stream not found", 404

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
    channels = read_channels_file()
    existing_streams = streams_table()
    for name, url in channels.items():
        info = fetch_info(url)
        if info:
            save_fetch_result(name, url, info)
            logger.info(f"Updated {name} via manual refresh")
        else:
            existing = existing_streams.get(name, {})
            repaired = repair_live_info(
                url,
                name,
                known_channel_url=existing.get("channel_url"),
                known_channel_id=existing.get("channel_id"),
            )
            save_fetch_result(name, url, repaired, update_channels=True)
            logger.warning(f"Repair refresh result for {name}: {repaired.get('status')}")

    set_last_update()

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
            stream_data = streams_table().get(name, {})
            info = repair_live_info(
                url,
                name,
                known_channel_url=stream_data.get("channel_url"),
                known_channel_id=stream_data.get("channel_id"),
            )
            new_url = save_fetch_result(name, url, info, update_channels=True)
            logger.info(
                f"Live check for {name}: {info.get('status')} "
                f"({url} -> {new_url})"
            )
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
    # Simple healthcheck endpoint for Docker/Portainer
    return "OK", 200
