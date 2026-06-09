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
- Non-blocking startup refresh
- Per-stream `Check Live` repair button
- Automatic repair for changed YouTube live broadcast URLs
- Channel `/streams` discovery for replacement live broadcast URLs
- Automatic single-candidate and unique-title matching
- Dashboard selection for ambiguous multiple live broadcasts
- On-demand repair when a configured stream has no cached M3U8
- Shared per-stream repair with timeout and failed-repair cooldown
- Shared global refresh lock to prevent overlapping refresh jobs
- Hourly due-stream scheduling with configurable global and per-stream intervals
- Persisted dashboard refresh setting with environment-default reset
- Inline source editing for failed streams
- Normalized new handles and YouTube-only source validation
- Paginated access logs
- Persistent YouTube channel ID and channel URL discovery
- Atomic, locked database writes to protect the stream cache
- Seven-day access-log retention
- Readiness-aware health check
- Access logs grouped by stream and client IP
- Docker image published to GitHub Container Registry
- Portainer-friendly `docker-compose.yml`

## How Live Link Repair Works

Some YouTube livestreams keep the same channel but change their `watch?v=...` broadcast URL. When that happens, an old saved video URL can stop returning a valid M3U8 link.

This app handles that in two ways:

1. It first tries the saved URL.
2. If the saved URL fails, it checks recent broadcasts from the channel's `/streams` page and verifies which entries are currently live.
3. It also tries to discover the channel's current live page, including:
   - `https://www.youtube.com/@handle/live`
   - `https://www.youtube.com/channel/CHANNEL_ID/live`
   - `https://www.youtube.com/c/name/live`
   - `https://www.youtube.com/user/name/live`

If a new live stream is found, the app updates both:

- `db.json`, for the current cached redirect
- `channels.txt`, so the repair survives container restarts

If one current live broadcast is found, it is selected automatically. When multiple broadcasts are live, the app automatically selects only a uniquely strong title match to the previous broadcast. Ambiguous choices are shown in a `Select Live Stream` dropdown on the dashboard.

If one stream cannot be repaired, it is marked `no_live_found`. Other streams continue to refresh and serve normally.

Whenever a stream works, the app also stores its stable YouTube channel URL and channel ID. Future repairs use that saved channel identity before guessing from the local stream name. This allows a stream such as local name `atv` to be repaired through its real YouTube handle or channel ID even if the old `watch?v=...` video becomes private or deleted.

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

The client is redirected to the latest cached YouTube M3U8 URL.

When a configured stream has no cached M3U8, `/stream` automatically starts or joins one background repair attempt for that stream. Requests wait up to 30 seconds. If repair cannot complete, the endpoint returns `503 Service Unavailable` with `Retry-After: 30`. Failed repairs enter a five-minute in-memory cooldown to reduce repeated YouTube queries.

Unknown stream handles still return `404 Stream not found`.

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

Database updates use file locking and atomic replacement so scheduled refreshes and access logging cannot overwrite each other's changes or leave a partially written `db.json`.

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

The environment default is configured with:

```text
UPDATE_INTERVAL_HOURS=5
```

Allowed values are whole hours from `1` through `5`. The dashboard can persist an override in `/data/settings.json` or reset to the environment default.

Each stream can optionally override the global interval using a third `channels.txt` column:

```text
atv,https://www.youtube.com/@atvturkiye/live,2
earthtv,https://www.youtube.com/watch?v=HfgIFGbdGJ0
```

The scheduler checks hourly and refreshes only streams whose configured interval has elapsed. `Refresh` on the dashboard always refreshes every stream immediately.

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

The health check verifies that the database is readable, the data directory is writable, and the scheduler is running. It does not require any YouTube stream to be online. Unhealthy responses return only `UNHEALTHY` with HTTP `503`; detailed reasons are written to Docker logs.

## Logging

Logs are printed to stdout for Portainer/Docker log viewing. Typical events include:

```text
[CACHE] Updated stream successfully
[REPAIR] Trying live candidate
[WARN] Repair refresh result
[ERROR] Failed to fetch info
```

Access logs are stored in `db.json` and visible from the dashboard.

Access logs include request outcomes such as `redirected`, `repair_failed`, `repair_timeout`, and `cooldown`. Entries older than seven days are pruned during global refresh.

## Credits

Built with:

- Flask
- yt-dlp
- APScheduler
- Gunicorn
- Deno
