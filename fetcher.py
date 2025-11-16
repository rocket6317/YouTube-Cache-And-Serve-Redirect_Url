import yt_dlp
import logging
from db import update_stream
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

def fetch_info(url):
    import yt_dlp
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'forcejson': True,
        'extract_flat': False  # ✅ Must be False to get stream URLs
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "url": info.get("url"),
        "m3u8": info.get("url"),  # ✅ Ensure this is set
        "channel": info.get("channel") or info.get("uploader"),
        "title": info.get("title")
    }

def extract_name(url):
    if '@' in url:
        return url.split('@')[-1].split('/')[0]
    elif 'watch?v=' in url:
        video_id = parse_qs(urlparse(url).query).get('v', [''])[0]
        return f"video_{video_id}"
    else:
        return "unknown"

def process_channels():
    with open("channels.txt") as f:
        urls = [line.strip() for line in f if line.strip()]
    for url in urls:
        name = extract_name(url)
        try:
            info = fetch_info(url)
            m3u8 = info.get("url")
            channel_name = info.get("channel") or info.get("uploader") or name
            update_stream(name, url, m3u8, channel_name)
            print(f"[CACHE] {channel_name} cached as {name}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
