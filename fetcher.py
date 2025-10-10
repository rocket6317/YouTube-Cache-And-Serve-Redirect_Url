import yt_dlp
from db import update_stream
from urllib.parse import urlparse, parse_qs

def fetch_m3u8(url):
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'force_generic_extractor': False,
        'format': 'best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get('url')

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
                    m3u8 = fetch_m3u8(url)
                    update_stream(name, url, m3u8)
                    print(f"Updated {name}")
                except Exception as e:
                    print(f"Error processing {url}: {e}")