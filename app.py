from flask import Flask, redirect, request, render_template
from db import init_db, get_stream
from scheduler import start_scheduler
from fetcher import process_channels
from tinydb import TinyDB
from config import DB_PATH
import logging

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

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
        logger.info(f"[SERVE] Redirecting '{name}' to {m3u8}")
        return redirect(m3u8)
    logger.warning(f"[MISS] Stream '{name}' not found")
    return 'Stream not found', 404

@app.route('/dashboard')
def dashboard():
    db = TinyDB(DB_PATH)
    streams = db.all()
    return render_template('dashboard.html', streams=streams)

if __name__ == '__main__':
    app.run()
