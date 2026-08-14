import logging
import os
from flask import Flask, request, redirect, render_template, url_for, Response, flash
from datetime import datetime, timedelta
from db import (
    get_stream, streams_table, update_stream, delete_stream, clear_stream_source,
    set_stream_short_url,
    log_access, get_access_log,
    read_channels_file, read_channel_configs, write_channels_file, load_db
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
from stream_service import cached_youtube_stream_is_stale, repair_stream, save_fetch_result
from settings import get_global_interval, reset_global_interval, set_global_interval
from validation import is_m3u8_url, is_youtube_url, normalize_handle, parse_interval
from yourls import create_short_url

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
    streams = streams_table()
    stream_data = streams.get(name, {})
    channel_configs = read_channel_configs()
    configured_channels = read_channels_file()
    config = channel_configs.get(name, {})
    interval = config.get("refresh_hours") or get_global_interval()
    url = get_stream(name)

    if url and cached_youtube_stream_is_stale(stream_data, interval):
        outcome = repair_coordinator.request(name, timeout=30)
        if outcome == "redirected":
            url = get_stream(name) or url
        else:
            logger.warning(f"Serving stale cached URL for {name}; refresh result: {outcome}")

    if url:
        log_access(name, ip, outcome="redirected")
        # Removed noisy INFO log line here
        return redirect(url)

    if name not in configured_channels and name not in channel_configs and name not in streams:
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
    channel_configs = read_channel_configs()
    db = load_db()
    lu = db.get("last_update")
    nu = None
    lu_fmt = None
    nu_fmt = None

    if lu:
        lu_dt = datetime.fromisoformat(lu)
        nu_dt = lu_dt + timedelta(hours=get_global_interval())
        lu_fmt = lu_dt.strftime("%H:%M:%S on %d-%m-%Y")
        nu_fmt = nu_dt.strftime("%H:%M:%S on %d-%m-%Y")

    logger.info("Dashboard accessed")
    return render_template(
        "dashboard.html",
        streams=streams,
        channel_configs=channel_configs,
        stream_base_url=os.getenv("PUBLIC_STREAM_BASE_URL") or request.url_root.rstrip("/"),
        global_interval=get_global_interval(),
        environment_interval=UPDATE_INTERVAL_HOURS,
        last_update=lu_fmt,
        next_update=nu_fmt
    )

@app.route("/dashboard/refresh", methods=["POST"])
def refresh():
    logger.info("Manual dashboard refresh triggered")
    if refresh_from_channels_txt(source="manual", force=True):
        flash("Refresh completed.", "success")
    else:
        flash("Refresh already running.", "warning")
    return redirect(url_for("dashboard"))

@app.route("/dashboard/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = normalize_handle(request.form.get("name", ""))
        url = request.form.get("url", "").strip()
        fallback_url = request.form.get("fallback_url", "").strip()
        try:
            interval = parse_interval(request.form.get("refresh_hours"))
        except (ValueError, TypeError):
            flash("Refresh interval must be Default or between 1 and 5 hours.", "warning")
            return redirect(url_for("add"))
        if not name or not url:
            flash("Handle and YouTube URL are required.", "warning")
            return redirect(url_for("add"))
        channels = read_channel_configs()
        if any(normalize_handle(existing_name) == name for existing_name in channels):
            flash(f"Handle '{name}' already exists.", "warning")
            return redirect(url_for("add"))
        if not is_youtube_url(url):
            flash("Source must be a valid YouTube URL.", "warning")
            return redirect(url_for("add"))
        if fallback_url and not is_m3u8_url(fallback_url):
            flash("Fallback must be a valid HTTP(S) M3U8 URL.", "warning")
            return redirect(url_for("add"))

        info = fetch_info(url)
        if info:
            save_fetch_result(name, url, info)
            logger.info(f"Added new stream {name}")
        else:
            update_stream(name, url, None, None, status="failed", last_error="Initial fetch failed")
            logger.warning(f"Failed to add stream {name}")

        channels[name] = {"url": url, "refresh_hours": interval}
        if fallback_url:
            channels[name]["fallback_url"] = fallback_url
        write_channels_file(channels)
        stream_available = bool(info) or repair_stream(name)
        short_url = create_short_url(name)
        if short_url:
            set_stream_short_url(name, short_url)
        if stream_available:
            flash(f"Added stream {name}.", "success")
        else:
            status = streams_table().get(name, {}).get("status")
            if status == "selection_required":
                flash(f"Added {name}; select the intended live stream.", "warning")
            else:
                flash(f"Added {name}; no current live stream was found.", "warning")
        if not short_url and os.getenv("YOURLS_API_URL"):
            flash(f"Stream added, but a short URL could not be created for {name}.", "warning")
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
        channels = read_channel_configs()
        if name in channels:
            del channels[name]
            write_channels_file(channels)
        logger.info(f"Deleted stream {name}")
        flash(f"Deleted stream {name}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/settings", methods=["POST"])
def update_settings():
    if request.form.get("reset"):
        reset_global_interval()
        flash(f"Global refresh reset to environment default ({UPDATE_INTERVAL_HOURS} hours).", "success")
    else:
        try:
            set_global_interval(request.form.get("update_interval_hours"))
            flash("Global refresh interval updated.", "success")
        except (ValueError, TypeError):
            flash("Global refresh interval must be between 1 and 5 hours.", "warning")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/interval", methods=["POST"])
def update_interval():
    name = request.form.get("name", "").strip()
    configs = read_channel_configs()
    if name not in configs:
        flash("Stream not found.", "warning")
        return redirect(url_for("dashboard"))
    try:
        configs[name]["refresh_hours"] = parse_interval(request.form.get("refresh_hours"))
        write_channels_file(configs)
        flash(f"Refresh interval updated for {name}.", "success")
    except (ValueError, TypeError):
        flash("Refresh interval must be Default or between 1 and 5 hours.", "warning")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/fallback", methods=["POST"])
def update_fallback():
    name = request.form.get("name", "").strip()
    fallback_url = request.form.get("fallback_url", "").strip()
    configs = read_channel_configs()
    if name not in configs:
        flash("Stream not found.", "warning")
        return redirect(url_for("dashboard"))
    if fallback_url and not is_m3u8_url(fallback_url):
        flash("Fallback must be a valid HTTP(S) M3U8 URL.", "warning")
        return redirect(url_for("dashboard"))
    if fallback_url:
        configs[name]["fallback_url"] = fallback_url
    else:
        configs[name].pop("fallback_url", None)
    write_channels_file(configs)
    if repair_stream(name):
        flash(f"Fallback updated and stream refreshed for {name}.", "success")
    else:
        flash(f"Fallback updated for {name}; no stream is currently available.", "warning")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/edit-source", methods=["POST"])
def edit_source():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    streams = streams_table()
    configs = read_channel_configs()
    stream_data = streams.get(name, {})
    status = stream_data.get("status", "failed" if not stream_data.get("m3u8") else "ok")
    if name not in configs or status not in ("failed", "no_live_found"):
        flash("Source editing is available only for failed streams.", "warning")
        return redirect(url_for("dashboard"))
    if not is_youtube_url(url):
        flash("Source must be a valid YouTube URL.", "warning")
        return redirect(url_for("dashboard"))
    configs[name]["url"] = url
    write_channels_file(configs)
    clear_stream_source(name, url)
    if repair_stream(name):
        flash(f"Source updated and live stream found for {name}.", "success")
    else:
        flash(f"Source updated for {name}; no live stream is currently available.", "warning")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/select-live", methods=["POST"])
def select_live():
    name = request.form.get("name", "").strip()
    selected_url = request.form.get("url", "").strip()
    stream = streams_table().get(name, {})
    configs = read_channel_configs()
    allowed_urls = {
        candidate.get("url")
        for candidate in stream.get("live_candidates", [])
        if candidate.get("url")
    }
    if name not in configs or selected_url not in allowed_urls:
        flash("Live stream selection is no longer available. Check Live again.", "warning")
        return redirect(url_for("dashboard"))
    info = fetch_info(selected_url, name)
    if not info or not (info.get("is_live") or info.get("live_status") == "is_live"):
        flash("The selected broadcast is no longer live. Check Live again.", "warning")
        return redirect(url_for("dashboard"))
    save_fetch_result(
        name,
        configs[name]["url"],
        info,
        channels=configs,
        update_channels=True,
    )
    flash(f"Selected live stream for {name}.", "success")
    return redirect(url_for("dashboard"))

@app.route("/logs")
def logs():
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    all_logs = sorted(get_access_log(), key=lambda entry: entry.get("timestamp", ""), reverse=True)
    start = (page - 1) * 200
    raw_logs = all_logs[start:start + 200]
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
    return render_template(
        "logs.html",
        grouped_logs=grouped,
        page=page,
        has_previous=page > 1,
        has_next=start + 200 < len(all_logs),
    )

@app.route("/download_channels")
def download_channels():
    channels = read_channel_configs()
    lines = []
    for name, config in channels.items():
        line = f"{name},{config['url']}"
        if config.get("refresh_hours") is not None or config.get("fallback_url"):
            line += f",{config.get('refresh_hours') or ''}"
        if config.get("fallback_url"):
            line += f",{config['fallback_url']}"
        lines.append(line)
    content = "\n".join(lines)
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
