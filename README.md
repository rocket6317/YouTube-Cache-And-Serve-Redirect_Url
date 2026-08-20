# YouTube Livestream Redirector Dashboard

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/M4M31NTEGN)

A lightweight Flask dashboard that turns YouTube livestreams into stable local redirect URLs for IPTV players and other clients.

The app stores your stream list, extracts fresh YouTube HLS/M3U8 URLs with `yt-dlp`, and serves each stream through a stable endpoint:

```text
https://your-domain/stream?name=channelname
```

## Features

- Stable `/stream?name=...` playback URLs for IPTV clients
- Dashboard to add, delete, refresh, repair, and inspect streams
- `yt-dlp` based M3U8 extraction
- Automatic scheduled refresh
- Non-blocking startup refresh
- Per-stream `Check Live` repair button
- Automatic repair for changed YouTube live broadcast URLs
- Channel `/streams` discovery for replacement live broadcast URLs
- Automatic single-candidate and unique-title matching
- Dashboard selection for ambiguous multiple live broadcasts
- Optional YOURLS short URLs for newly added streams, with saved dashboard links
- On-demand repair when a configured stream has no cached M3U8
- Five-minute cached playback validation for Googlevideo manifests and media segments
- Adaptive YouTube HLS support with separate audio and video playlists
- Automatic signed-playlist refresh during adaptive playback
- Direct YouTube media delivery; the app proxies only small HLS playlists
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

This app handles that through a staged repair flow:

1. It first tries the saved URL and accepts it only when YouTube reports it as currently live.
2. If the saved URL fails or has ended, it checks recent broadcasts from the channel's `/streams` page and verifies which entries are currently live.
3. It also checks the channel's current `/live` page, including:
   - `https://www.youtube.com/@handle/live`
   - `https://www.youtube.com/channel/CHANNEL_ID/live`
   - `https://www.youtube.com/c/name/live`
   - `https://www.youtube.com/user/name/live`

If a new live stream is found, the app updates both:

- `db.json`, for the current cached redirect
- `channels.txt`, so the repair survives container restarts

If one current live broadcast is found, it is selected automatically. When multiple broadcasts are live, the app automatically selects only a uniquely strong title match to the previous broadcast.

When multiple current broadcasts remain ambiguous:

- The stream becomes `selection_required`
- Other configured streams continue working normally
- The dashboard shows a `Select Live Stream` dropdown with candidate titles and YouTube URLs
- The selected broadcast becomes the saved source and preferred title for future repairs

If one stream cannot be repaired, it is marked `no_live_found`. Other streams continue to refresh and serve normally.

Whenever a stream works, the app also stores its stable YouTube channel URL and channel ID. Future repairs use that saved channel identity before guessing from the local stream name. This allows a stream such as local name `atv` to be repaired through its real YouTube handle or channel ID even if the old `watch?v=...` video becomes private or deleted.

Discovery checks a limited number of recent `/streams` entries sequentially to reduce unnecessary YouTube requests. Ended public videos are not accepted as current live streams.

## Dashboard

Default local dashboard:

```text
http://localhost:6095/dashboard
```

Main controls:

- `Add Channel`: add a new local stream name and YouTube URL
- `Refresh`: refresh all streams and repair failed live links when possible
- `Global refresh`: set the default interval from 1 through 5 hours or reset it to the environment default
- `Download channels.txt`: download the current source list
- `View Access Logs`: inspect stream access by IP and timestamp

Per-stream controls:

- `Copy`: copy the current extracted M3U8 URL
- `Download`: download a one-line `.m3u8` file
- `Interval`: use the global default or override it from 1 through 5 hours
- `Check Live`: immediately re-check one stream and repair changed live URLs
- `Edit Source`: replace the YouTube source for a failed or `no_live_found` stream
- `Select Live Stream`: choose the intended broadcast when multiple current live candidates are ambiguous
- `Delete`: remove the stream

New local handles are normalized to lowercase URL-safe slugs. Duplicate normalized handles and non-YouTube source URLs are rejected. Existing handles remain unchanged for backward compatibility.

When YOURLS integration is configured, adding a stream also requests a short URL for its stable IPTV URL. The local handle is used as the preferred keyword:

```text
https://stream.example.com/stream?name=example-channel
https://short.example.com/example-channel
```

YOURLS may return a different available keyword when the preferred keyword is already in use. Stream names containing spaces and other URL-sensitive characters are encoded in the destination URL, so a saved name such as `Now TV` continues to resolve correctly.

The returned short URL is saved with the stream and displayed below its stable IPTV URL. It remains attached to the stream during refresh and live-link repair operations. A YOURLS failure does not prevent the stream from being added or affect other configured streams.

YOURLS links are created when new streams are added. Streams that existed before YOURLS was configured are not automatically backfilled; they can continue using their stable IPTV URLs unless short links are created separately.

## Playback Usage

Use the local handle from the dashboard:

```text
https://your-domain/stream?name=channelname
http://localhost:6095/stream?name=channelname
```

Legacy combined YouTube streams redirect the client to the latest cached M3U8 URL, preserving the original behavior for existing working channels.

When YouTube supplies separate audio and video playlists, `/stream` returns a small stable master M3U8. Its internal audio and video playlist URLs are reloaded through the app, so a scheduled or on-demand refresh can replace expired signed YouTube URLs during playback. Media segments still travel directly from YouTube to the IPTV client; the application does not relay the video payload.

Adaptive media playlists are reduced to a rolling 12-segment window before being returned. This keeps playlist requests small while maintaining about one minute of live buffering.

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
- `settings.json`, when a dashboard global interval override is saved

This keeps persistent data separate from `/app`, so updating the container image actually updates the application code.

Database updates use file locking and atomic replacement so scheduled refreshes and access logging cannot overwrite each other's changes or leave a partially written `db.json`.

`channels.txt` format:

```text
local_name,https://www.youtube.com/@channel/live
local_name_2,https://www.youtube.com/watch?v=VIDEO_ID
local_name_3,https://www.youtube.com/watch?v=VIDEO_ID,2
local_name_4,https://www.youtube.com/@channel/live,1,https://fallback.example.com/live.m3u8
```

The optional third column is that stream's refresh interval in whole hours from `1` through `5`. Rows without it use the global default. Repairs and source edits preserve interval overrides.

The optional fourth column is a direct fallback M3U8 URL. The application always tries the YouTube source first. If no current YouTube live stream exists, it serves the fallback until a later scheduled or manual refresh finds YouTube live again. Leave the third column empty when using a fallback with the global interval:

```text
local_name,https://www.youtube.com/@channel/live,,https://fallback.example.com/live.m3u8
```

Fallback URLs can also be added, changed, or removed from the dashboard. They are stored in `channels.txt` and survive container updates.

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
      - PUBLIC_STREAM_BASE_URL=${PUBLIC_STREAM_BASE_URL:-}
      - YOURLS_API_URL=${YOURLS_API_URL:-}
      - YOURLS_USER=${YOURLS_USER:-}
      - YOURLS_PASS=${YOURLS_PASS:-}
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

GitHub Actions runs the Python test suite, then builds and publishes this image on every push to `main`.

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

The scheduler checks hourly and refreshes only streams whose configured interval has elapsed. Every attempted refresh resets that stream's schedule, including failed attempts. `Refresh` on the dashboard ignores intervals and refreshes every stream immediately.

Before serving a player, the application validates cached Googlevideo playback by reading the manifest and one byte from its newest media segment. Results are cached for five minutes. This check does not query a YouTube page or API, and it catches media authorization that becomes invalid before the signed URL's advertised expiry. An invalid stream receives one coordinated repair attempt; it is not served if repair fails. Age-due streams still refresh at their configured interval, and a previously validated playable URL can continue to be served if that scheduled refresh fails. Concurrent requests share repairs, and failed attempts enter a cooldown. Direct fallback M3U8 URLs are excluded from Googlevideo validation.

The container pins the tested `yt-dlp` 2026.08.19 release. This release supports YouTube's current adaptive live format, where extraction can return separate video and audio playlists instead of one combined URL. Dependency installation is deterministic; Docker builds no longer upgrade `yt-dlp` to an untested version automatically.

The Docker image also sets:

```text
YTDLP_EXTERNAL_JS=1
```

The Dockerfile installs Deno so `yt-dlp` can use an external JavaScript runtime when YouTube extraction needs it.

Optional YOURLS integration uses environment variables:

```text
PUBLIC_STREAM_BASE_URL=https://stream.example.com
YOURLS_API_URL=http://yourls-host/yourls-api.php
YOURLS_USER=yourls-api-user
YOURLS_PASS=yourls-api-password
```

All four values must be configured to enable shortening. `PUBLIC_STREAM_BASE_URL` must be the externally reachable base URL for this redirector, without `/dashboard` or `/stream`.

For each newly added stream, the app sends YOURLS the stable redirect URL rather than the temporary YouTube M3U8 URL. This means the short URL continues working when YouTube changes the broadcast URL or the cached M3U8 is refreshed. Existing matching YOURLS links are reused instead of duplicated.

Keep YOURLS credentials in the deployment environment or Portainer stack configuration. Do not commit them to the repository.

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

Access logs include request outcomes such as `redirected`, `repair_failed`, `repair_timeout`, and `cooldown`. Entries older than seven days are pruned during global refresh. The dashboard displays the newest 200 raw events per page before grouping them by stream and client IP.

## Credits

Built with:

- Flask
- yt-dlp
- APScheduler
- Gunicorn
- Deno
