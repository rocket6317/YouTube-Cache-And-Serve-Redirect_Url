# YouTube Livestream Redirector Dashboard

A lightweight Flask dashboard that turns YouTube livestreams into stable local redirect URLs for IPTV players and other clients.

The app stores your stream list, extracts fresh YouTube HLS/M3U8 URLs with `yt-dlp`, and serves each stream through a stable endpoint:

```text
https://your-domain/stream?name=channelname
```

## Features

- Stable `/stream?name=...` redirect URLs for IPTV clients
- Dashboard to add, delete, refresh, repair, and inspect streams
- `yt-dlp` based M3U8 extraction
- Automatic scheduled refresh
- Per-stream `Check Live` repair button
- Automatic repair for changed YouTube live broadcast URLs
- Access logs grouped by stream and client IP
- Docker image published to GitHub Container Registry
- Portainer-friendly `docker-compose.yml`

## How Live Link Repair Works

Some YouTube livestreams keep the same channel but change their `watch?v=...` broadcast URL. When that happens, an old saved video URL can stop returning a valid M3U8 link.

This app handles that in two ways:

1. It first tries the saved URL.
2. If the saved URL fails, it tries to discover the channel's current live page, including:
   - `https://www.youtube.com/@handle/live`
   - `https://www.youtube.com/channel/CHANNEL_ID/live`
   - `https://www.youtube.com/c/name/live`
   - `https://www.youtube.com/user/name/live`

If a new live stream is found, the app updates both:

- `db.json`, for the current cached redirect
- `channels.txt`, so the repair survives container restarts

If one stream cannot be repaired, it is marked `no_live_found`. Other streams continue to refresh and serve normally.

## Dashboard

Default local dashboard:

```text
http://localhost:6095/dashboard
```

Main controls:

- `Add Channel`: add a new local stream name and YouTube URL
- `Refresh`: refresh all streams and repair failed live links when possible
- `Download channels.txt`: download the current source list
- `View Access Logs`: inspect stream access by IP and timestamp

Per-stream controls:

- `Copy`: copy the current extracted M3U8 URL
- `Download`: download a one-line `.m3u8` file
- `Check Live`: immediately re-check one stream and repair changed live URLs
- `Delete`: remove the stream

## Redirect Usage

Use the local handle from the dashboard:

```text
https://your-domain/stream?name=channelname
http://localhost:6095/stream?name=channelname
```

The client is redirected to the latest cached YouTube M3U8 URL. If a stream has no working M3U8, that one stream returns `404 Stream not found`.

## Data Files

Runtime data is stored in `DATA_DIR`.

In Docker, the compose file sets:

```text
DATA_DIR=/data
```

The named Docker volume is mounted at `/data` and stores:

- `channels.txt`
- `db.json`
- `timestamps.txt`

This keeps persistent data separate from `/app`, so updating the container image actually updates the application code.

`channels.txt` format:

```text
local_name,https://www.youtube.com/@channel/live
local_name_2,https://www.youtube.com/watch?v=VIDEO_ID
```

## Docker And Portainer

The default compose file uses the published GHCR image:

```yaml
services:
  youtube-redirector:
    image: ghcr.io/rocket6317/youtube-cache-and-serve-redirect-url:latest
    ports:
      - "6095:6095"
    environment:
      - DATA_DIR=/data
      - YTDLP_EXTERNAL_JS=1
    volumes:
      - app_data:/data
```

Deploy with Docker Compose:

```bash
docker compose up -d
```

For Portainer:

1. Use this repository as the stack source, or paste the `docker-compose.yml`.
2. Redeploy the stack.
3. Pull/recreate the container when `main` is updated.

The image is published at:

```text
ghcr.io/rocket6317/youtube-cache-and-serve-redirect-url:latest
```

GitHub Actions builds and publishes this image on every push to `main`.

## Local Development

Clone the repository:

```bash
git clone https://github.com/rocket6317/YouTube-Cache-And-Serve-Redirect_Url.git
cd YouTube-Cache-And-Serve-Redirect_Url
```

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install --upgrade yt-dlp
```

Run locally:

```bash
python app.py
```

Local runtime files default to the current directory unless `DATA_DIR` is set.

## Configuration

Refresh interval is configured in `config.py`:

```python
UPDATE_INTERVAL_HOURS = 6
```

The Docker image also sets:

```text
YTDLP_EXTERNAL_JS=1
```

The Dockerfile installs Deno so `yt-dlp` can use an external JavaScript runtime when YouTube extraction needs it.

## Health Check

The container exposes:

```text
/health
```

Expected response:

```text
OK
```

## Logging

Logs are printed to stdout for Portainer/Docker log viewing. Typical events include:

```text
[CACHE] Updated stream successfully
[REPAIR] Trying live candidate
[WARN] Repair refresh result
[ERROR] Failed to fetch info
```

Access logs are stored in `db.json` and visible from the dashboard.

## Credits

Built with:

- Flask
- yt-dlp
- APScheduler
- Gunicorn
- Deno
