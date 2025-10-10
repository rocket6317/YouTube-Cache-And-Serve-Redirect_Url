from flask import Flask, redirect, request
from db import init_db, get_stream
from scheduler import start_scheduler
from fetcher import process_channels

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
        return redirect(m3u8)
    return 'Stream not found', 404

if __name__ == '__main__':
    app.run()