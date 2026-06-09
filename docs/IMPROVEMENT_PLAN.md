# YouTube Livestream Redirector Improvement Plan

Status: Approved for implementation  
Created: 2026-06-09  
Implementation approach: Two staged releases

## Purpose

Improve playback recovery, operational reliability, scheduling flexibility, and dashboard usability without over-engineering the project.

The project will continue using Flask, `yt-dlp`, JSON storage, `channels.txt`, APScheduler, Docker, GHCR, Portainer, and the existing manual DietPi deployment method.

## Guiding Decisions

- Cloudflare rules remain responsible for dashboard access protection.
- Failed refreshes immediately clear the cached M3U8; do not preserve the previous M3U8.
- JSON storage remains in place. Do not migrate to SQLite.
- Do not add notifications, rotating backups, Watchtower, Portainer webhooks, self-hosted GitHub runners, CSRF protection, or a combined M3U playlist.
- Refreshes remain sequential to reduce YouTube request bursts.
- Unavailable streams remain configured and are retried indefinitely.
- Production deployment remains manual using the previously tested DietPi Compose procedure.
- Deployment problems are corrected forward; do not automatically roll back.

## Stage 1: Reliability

### 1. On-Demand Repair From `/stream`

When `/stream?name=<handle>` is requested and no M3U8 is cached:

1. Start or join an on-demand repair for that stream.
2. Allow only one active repair per stream.
3. Concurrent requests wait for the same repair result.
4. Wait for up to 30 seconds.
5. If repair succeeds, return the normal redirect.
6. If repair is still running after 30 seconds, return:
   - HTTP `503 Service Unavailable`
   - `Retry-After: 30`
7. If repair fails, return `503`.
8. Apply a five-minute in-memory cooldown after failed repair.
9. Requests during cooldown return `503` without starting another YouTube query.
10. Repairs continue in the background if the initiating client disconnects.

On-demand repair runs only when the cached M3U8 is missing. It does not validate a cached M3U8 before redirecting.

Successful repairs continue replacing failed source URLs with the discovered stable channel `/live` URL while preserving the stream's configuration.

### 2. On-Demand Repair Access Logging

Log both successful and failed `/stream` requests.

Supported outcomes:

- `redirected`
- `repair_failed`
- `repair_timeout`
- `cooldown`

Successful direct redirects and successful repaired redirects both use `redirected`.

### 3. Global Refresh Locking

Use one shared global refresh lock for:

- Startup refresh
- Scheduled refresh
- Manual dashboard `Refresh All Now`

Only one global refresh may run at a time. Additional manual refresh attempts should return to the dashboard with a clear `Refresh already running` message.

Per-stream on-demand repair locks remain independent from the global refresh lock.

### 4. Non-Blocking Startup Refresh

The web application should become available immediately using the existing cache.

Startup refresh runs in the background under the global refresh lock. Slow YouTube responses must not delay:

- `/health`
- `/dashboard`
- Existing cached stream redirects

### 5. Seven-Day Access-Log Retention

Automatically prune access-log entries older than seven days during scheduled refresh.

Retain individual log events. Do not aggregate them.

### 6. Readiness Health Check

`/health` should verify:

- `db.json` can be read
- The configured data directory is writable
- The scheduler is running

The health endpoint must not require any YouTube stream to be online.

Public responses remain detail-free:

- Healthy: `OK`, HTTP `200`
- Unhealthy: `UNHEALTHY`, HTTP `503`

Detailed failure reasons go only to Docker logs.

### 7. CI Test Gate

GitHub Actions must run the Python test suite before building and publishing the Docker image.

Do not add a container startup smoke test or special CI startup mode. Do not otherwise change Docker tag/publishing behavior.

### Stage 1 Acceptance Criteria

- Missing-M3U8 requests trigger one shared per-stream repair.
- Concurrent requests do not create duplicate `yt-dlp` repair work.
- Repair timeout and cooldown responses use `503` and the agreed logging outcomes.
- Failed repair cooldown lasts five minutes in memory.
- Startup refresh no longer blocks application availability.
- Startup, scheduled, and manual global refreshes cannot overlap.
- Access logs older than seven days are pruned.
- `/health` performs the agreed readiness checks without exposing details.
- Python tests must pass before image publishing.
- Existing active streams still redirect after deployment.

## Stage 2: Dashboard And Scheduling

### 1. Global Refresh Default

Support `UPDATE_INTERVAL_HOURS` as an environment-variable default.

Allow the dashboard to configure a persisted global default:

- Whole-hour values from 1 through 5
- Default value: 5 hours
- Dashboard value stored in `/data/settings.json`
- Dashboard value overrides the environment default
- Support reset to the environment default
- Changes apply immediately

### 2. Per-Stream Refresh Intervals

Each stream can optionally override the global default.

Allowed values:

- `Default`
- `1 hour`
- `2 hours`
- `3 hours`
- `4 hours`
- `5 hours`

Extend `channels.txt` with an optional third column:

```text
handle,youtube_url,refresh_hours
atv,https://www.youtube.com/@atvturkiye/live,2
earthtv,https://www.youtube.com/watch?v=HfgIFGbdGJ0,5
sozcutv,https://www.youtube.com/@Sozcutelevizyonu/live
```

Two-column rows remain valid and use the global default.

Source repairs and source edits must preserve interval overrides.

### 3. Due-Stream Scheduling

- Scheduler runs once per hour.
- It refreshes only streams that are due.
- Refreshes remain sequential.
- Every refresh attempt, successful or failed, resets that stream's next scheduled refresh time.
- Successful on-demand repair also resets the stream's schedule.
- Failed streams wait for their normal configured interval. Do not retry them hourly.
- Global `Refresh All Now` ignores intervals and refreshes every stream immediately.
- Unavailable streams remain configured and are retried indefinitely.

### 4. Handle Validation

For newly added streams:

- Normalize handles to lowercase URL-safe slugs.
- Reject duplicate normalized handles with a clear error.
- Preserve existing handles for backward compatibility.
- Handles are immutable after creation.
- Reject non-YouTube source URLs.
- Keep current behavior for temporarily unavailable valid YouTube URLs.

### 5. Inline Source Editing

- Add inline `Edit Source` only for failed or `no_live_found` streams.
- Preserve the immutable handle.
- Preserve the stream interval override.
- Accept the replacement YouTube URL immediately.
- Clear stale M3U8 and channel identity.
- Validate immediately.
- If unavailable, keep it as failed/no-live and retry on schedule.
- Do not add a separate manually configured stable-channel field.

### 6. Dashboard Feedback

Add compact flash messages for dashboard actions, including:

- Success
- Validation failure
- Duplicate handle
- Repair success/failure
- Refresh already running
- Settings update result

Delete remains immediate without a confirmation prompt.

Keep source editing, global interval configuration, and per-stream intervals inline on the existing dashboard. Do not add separate settings or edit pages.

### 7. Access-Log Pagination

- Retain the existing grouped-by-channel-and-IP display.
- Sort newest events first.
- Each page contains the newest 200 raw events before grouping.
- Add Previous/Next navigation.

### Stage 2 Acceptance Criteria

- Global default interval is configurable from environment and dashboard.
- Dashboard default persists, overrides environment, and can be reset.
- Per-stream optional intervals persist in the optional third `channels.txt` column.
- Hourly scheduler refreshes only due streams.
- Attempts reset their stream schedule.
- `Refresh All Now` continues refreshing every stream.
- New handles are normalized and duplicate normalized handles are rejected.
- Non-YouTube URLs are rejected.
- Existing handles remain unchanged and immutable.
- Failed/no-live streams can edit source inline while preserving handle and interval.
- Dashboard actions provide clear flash feedback.
- Logs paginate 200 raw events per page while retaining grouped display.

## Explicit Non-Goals

The following are intentionally excluded:

- Application login or authorization changes
- Preserving last-known M3U8 after refresh failure
- Cached-M3U8 HTTP validation on every request
- Expiry-aware refresh logic
- SQLite migration
- Automatic backups
- Telegram or other notifications
- Watchtower
- Portainer deployment webhook
- Self-hosted GitHub Actions runner
- Automatic production deployment
- Automatic rollback
- Combined M3U playlist endpoint
- CSRF protection
- Aggregated access logs
- Concurrent multi-stream refresh
- Separate dashboard settings/edit pages
- Manual stable-channel identity field
- Displaying deployed application version
- Container startup smoke test in CI

## Deployment Procedure

Production deployment remains manual and uses the tested DietPi Compose method.

Before each deployment:

1. All automated tests pass.
2. GitHub Actions successfully publishes the new image.
3. Back up the existing production `channels.txt` and `db.json`.

Deploy using the Portainer-managed Compose file and the existing project name:

```bash
sudo sh -c \
  "cd /path/to/portainer/compose/stack \
  && docker compose -p youtube-redirector pull youtube-redirector \
  && docker compose -p youtube-redirector up -d --force-recreate youtube-redirector"
```

After deployment:

1. Container becomes healthy.
2. Dashboard responds.
3. Previously active streams still return redirects.
4. New behavior is explicitly tested.
5. Any failure is diagnosed and corrected forward without automatic rollback.

Important: Always pass `-p youtube-redirector`. Without it, Compose derives project name `101` and attempts to create the wrong volume and container set.

## Implementation Order

1. Implement and test Stage 1.
2. Publish the Stage 1 image.
3. Back up production data.
4. Manually deploy Stage 1 using the tested Compose method.
5. Verify Stage 1 acceptance criteria in production.
6. Implement and test Stage 2.
7. Publish and manually deploy Stage 2.
8. Verify Stage 2 acceptance criteria in production.
