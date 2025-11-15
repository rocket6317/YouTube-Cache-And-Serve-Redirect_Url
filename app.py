import logging
import ipaddress
from datetime import timedelta
from flask import Flask, redirect, request, render_template

from db import init_db, get_stream, delete_stream, log_access, get_access_log, get_last_updated
from scheduler import start_scheduler
from fetcher import process_channels
from config import UPDATE_INTERVAL_HOURS

# --- Logging setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class MinimalFilter(logging.Filter):
    def filter(self, record):
        return any(tag in record.msg for tag in ['[CACHE]', '[SERVE]', '[ADD]', '[DELETE]', '[REFRESH]'])
logger.addFilter(MinimalFilter())

# --- Flask app must be defined BEFORE routes ---
app = Flask(__name__)

# --- Init data and scheduler ---
init_db()
process_channels()
start_scheduler()

# --- IP helpers ---
def _is_public_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        return False

def get_client_and_proxy_ips(req):
    # Prefer Cloudflare's direct header for client if present
    cf_client = req.headers.get('CF-Connecting-IP')
    if cf_client and _is_public_ip(cf_client):
        client_ip = cf_client.strip()
    else:
        xff = req.headers.get('X-Forwarded-For', '')
        chain = [i.strip() for i in xff.split(',') if i.strip()]
        client_ip = next((ip for ip in chain if _is_public_ip(ip)), None)
        if not client_ip and _is_public_ip(req.remote_addr):
            client_ip = req.remote_addr

    # Proxy (Cloudflare) is the last public IP in the chain
    proxy_ip = None
    for ip in reversed(chain):
        if _is_public_ip(ip):
            proxy_ip = ip
            break
    if not proxy_ip and _is_public_ip(req.remote_addr):
        proxy_ip = req.remote_addr

    return client_ip or 'unknown', proxy_ip or 'unknown'

# --- Routes ---
@app.route('/stream')
def stream():
    name = request.args.get('name')
    if not name:
        return 'Missing name parameter', 400
    m3u8 = get_stream(name)
    if m3u8:
        # Just log one IP (prefer X-Forwarded-For if present, else remote_addr)
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        log_access(name, ip)
        logger.info(f"[SERVE] {name} served to {ip}")
        return redirect(m3u8)
    logger.warning(f"[MISS] {name} not found")
    return 'Stream not found', 404

# ... other routes (dashboard, add, delete, refresh, logs) go here ...
