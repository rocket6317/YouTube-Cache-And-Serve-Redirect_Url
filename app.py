from flask import Flask, redirect, request, render_template
from db import init_db, get_stream, delete_stream, log_access, get_access_log, get_last_updated
from scheduler import start_scheduler
from fetcher import process_channels
from config import UPDATE_INTERVAL_HOURS
from datetime import timedelta
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class MinimalFilter(logging.Filter):
    def filter(self, record):
        return any(tag in record.msg for tag in ['[CACHE]', '[SERVE]', '[ADD]', '[DELETE]', '[REFRESH]'])

logger.addFilter(MinimalFilter())

app = Flask(__name__)
init_db()
process_channels()
start_scheduler()

@app.route('/stream')
def stream():
    name = request.args.get('name')
    if not name:
        return 'Missing name parameter', 400
    m3u8 = get_stream(name)
    if m3u8:
        proxy_ip = request.remote_addr
        client_ip = request.headers.get('X-Forwarded-For', proxy_ip)
        log_access(name, client_ip, proxy_ip)
        logger.info(f"[SERVE] {name} served to client {client_ip} via proxy {proxy_ip}")
        return redirect(m3u8)
    logger.warning(f"[MISS] {name} not found")
    return 'Stream not found', 404

@app.route('/dashboard')
def dashboard():
    from db import streams
    message = request.args.get('message')

    last_updated = get_last_updated()
    next_update = (last_updated + timedelta(hours=UPDATE_INTERVAL_HOURS)) if last_updated else None

    return render_template(
        'dashboard.html',
        streams=streams.values(),
        last_updated=last_updated.strftime('%Y-%m-%d %H:%M:%S UTC') if last_updated else 'Unknown',
        next_update=next_update.strftime('%Y-%m-%d %H:%M:%S UTC') if next_update else 'Unknown',
        message=message
    )

@app.route('/dashboard/add', methods=['GET', 'POST'])
def add_stream():
    if request.method == 'POST':
        url = request.form.get('url')
        if url:
            with open('channels.txt', 'a') as f:
                f.write(url.strip() + '\n')
            process_channels()
            name = url.split('@')[-1].split('/')[0] if '@' in url else url
            logger.info(f"[ADD] {name} added")
            return redirect('/dashboard?message=✅ Stream added and cached')
    return render_template('add.html')

@app.route('/dashboard/delete', methods=['POST'])
def delete():
    name = request.form.get('name')
    if name:
        delete_stream(name)
        logger.info(f"[DELETE] {name} removed")
    return redirect('/dashboard?message=🗑️ Stream deleted')

@app.route('/dashboard/refresh', methods=['POST'])
def refresh():
    process_channels()
    logger.info("[REFRESH] Manual refresh triggered")
    return redirect('/dashboard?message=✅ Links refreshed successfully')

@app.route('/dashboard/logs')
def logs():
    access_data = get_access_log()
    from db import streams
    return render_template('logs.html', access_data=access_data, streams=streams)
