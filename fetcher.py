import yt_dlp
import logging
from db import update_stream
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

def fetch_info(url):
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'force_generic_extractor': False,
        'format': 'bestvideo+bestaudio/best',
        'extractor_args': {
            'youtube': ['ejs=enable', 'player_client=web']
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

def extract_name(url):
    if '@' in url:
        return url.split('@')[-1].split('/')[0]
    elif 'watch?v=' in url:
        video_id = parse_qs(urlparse(url).query).get('v', [''])[0]
        return f"video_{video_id}"
    else:
        return "unknown"

def process_channels(file_path='channels.txt'):
    with open(file_path, 'r') as f:
        for line in f:
            url = line.strip()
            if url:
                name = extract_name(url)
                try:
                    info = fetch_info(url)
                    m3u8 = info.get('url')
                    title = info.get('title', name)  # fallback to internal name
                    update_stream(name, url, m3u8, title)
                    logger.info(f"[CACHE] {title} updated")
                except Exception as e:
                    logger.warning(f"[ERROR] Failed to cache {name}: {e}")
