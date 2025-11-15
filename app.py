from flask import Flask, request, redirect, render_template
from db import init_db, get_stream, log_access, get_access_log, delete_stream
from fetcher import process_channels
from scheduler import start_scheduler

app = Flask(__name__)

# ✅ Initialize DB and fetch streams immediately
init_db()
process_channels()
start_scheduler()

@app.route("/")
def home():
    return redirect("/dashboard")

@app.route("/stream")
def stream():
    name = request.args.get("name")
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    url = get_stream(name)
    if url:
        log_access(name, ip)
        return redirect(url)
    return "Stream not found", 404

@app.route("/dashboard")
def dashboard():
    from db import streams
    return render_template("dashboard.html", streams=streams)

@app.route("/logs")
def logs():
    logs = get_access_log()
    return render_template("logs.html", logs=logs)

@app.route("/dashboard/delete", methods=["POST"])
def delete():
    name = request.form.get("name")
    delete_stream(name)
    return redirect("/dashboard")

@app.route("/dashboard/refresh", methods=["POST"])
def refresh():
    process_channels()
    return redirect("/dashboard")

@app.route("/dashboard/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        url = request.form.get("url")
        from fetcher import fetch_info, extract_name
        name = extract_name(url)
        try:
            info = fetch_info(url)
            m3u8 = info.get("url")
            channel_name = info.get("channel") or info.get("uploader") or name
            from db import update_stream
            update_stream(name, url, m3u8, channel_name)
        except Exception:
            pass
        return redirect("/dashboard")
    return render_template("add.html")
