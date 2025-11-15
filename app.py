import ipaddress

def _is_public_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        return False

def get_client_and_proxy_ips(request):
    # Prefer Cloudflare's direct header for client if present
    cf_client = request.headers.get('CF-Connecting-IP')
    if cf_client and _is_public_ip(cf_client):
        client_ip = cf_client.strip()
    else:
        # Parse X-Forwarded-For chain: "client, cloudflare, ... (ascending hops)"
        xff = request.headers.get('X-Forwarded-For', '')
        chain = [i.strip() for i in xff.split(',') if i.strip()]
        # Client is the first public IP
        client_ip = next((ip for ip in chain if _is_public_ip(ip)), None)
        if not client_ip and _is_public_ip(request.remote_addr):
            client_ip = request.remote_addr

    # Proxy (Cloudflare) is the last public IP in the chain
    xff = request.headers.get('X-Forwarded-For', '')
    chain = [i.strip() for i in xff.split(',') if i.strip()]
    proxy_ip = None
    for ip in reversed(chain):
        if _is_public_ip(ip):
            proxy_ip = ip
            break

    # Fallback: use remote_addr only if it's public (ignore Docker/private)
    if not proxy_ip and _is_public_ip(request.remote_addr):
        proxy_ip = request.remote_addr

    return client_ip or 'unknown', proxy_ip or 'unknown'

@app.route('/stream')
def stream():
    name = request.args.get('name')
    if not name:
        return 'Missing name parameter', 400
    m3u8 = get_stream(name)
    if m3u8:
        client_ip, proxy_ip = get_client_and_proxy_ips(request)
        log_access(name, client_ip, proxy_ip)
        logger.info(f"[SERVE] {name} served to client {client_ip} via proxy {proxy_ip}")
        return redirect(m3u8)
    logger.warning(f"[MISS] {name} not found")
    return 'Stream not found', 404
