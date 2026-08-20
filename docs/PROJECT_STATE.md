# Project State

Last verified: 2026-08-20

## Current Release

- Release: `20.08.26 - v1.4.0`
- Tag: `20.08.26`
- Commit: `6df5bb221a8b6eca89d2c7f7e823e794ab4dff88`
- Container image digest: `sha256:20fe0c166125b68415f029ffd47671fbaa0808f4be1050dfaba88fce7002914e`
- Supported architectures: `linux/arm64` and `linux/amd64`

The release is deployed with Docker Compose on a Linux host. Runtime state is
mounted at `/data`, separate from the application image, so container updates do
not replace channel configuration or cached stream metadata.

Host addresses, host filesystem paths, credentials, and private service URLs are
intentionally excluded from this public document.

## Playback Model

The stable client endpoint is:

```text
/stream?name=<local-handle>
```

Two upstream playback formats are supported:

1. Legacy combined HLS streams retain the original direct-redirect behavior.
2. Adaptive streams return an internal master playlist referencing stable audio
   and video playlist endpoints.

For adaptive playback, the application reloads the signed upstream playlists and
can repair expired URLs during an active session. Media segments are delivered
directly from YouTube to the client; the application does not proxy video data.
Upstream DVR playlists are reduced to a rolling 12-segment live window.

## Refresh And Recovery

- Global and per-stream refresh intervals remain configurable from one through
  five hours.
- Changed `watch?v=` broadcasts are rediscovered through stored channel identity,
  `/streams`, and `/live` sources.
- Ambiguous channels with multiple live broadcasts require dashboard selection.
- Concurrent playback repairs share one per-stream repair operation.
- Failed repairs affect only the requested stream; other configured streams keep
  serving normally.
- Direct fallback M3U8 URLs remain available for channels that configure one.

## Verification

- The complete automated suite passes: 58 tests.
- Dependency installation was verified in a clean Python environment.
- The GitHub Actions workflow passed before publishing the multi-architecture
  image.
- Public playback probes verified AAC audio and H.264 1920x1080 video for six
  configured non-ATV streams.
- All seven stored stream records reported `status=ok` with adaptive audio and
  video playlists after deployment. ATV was intentionally excluded from the final
  playback probe.
- Container health returned HTTP 200 with zero restarts after deployment.

## Dependencies

- Python 3.13 container runtime
- Flask 3.0.3
- yt-dlp 2026.08.19, pinned to the tested release
- m3u8 6.0.0
- APScheduler 3.10.4
- Gunicorn 23.0.0
- Deno for yt-dlp's external JavaScript runtime

## Rollback

The pre-adaptive implementation is preserved as:

- Release/tag: `pre-adaptive-hls-20260820`
- Commit: `5df0e8722ff3aa0be5a8e7b5e0b94ce620a12863`
- Image digest: `sha256:1d001fb4a6e3ddc5a3b01b6b541983e6f6dced1e965b31b155a6b5033467b50d`

Before deployment, back up the complete `/data` mount and Compose configuration.
Rollback consists of restoring that data snapshot and recreating the service with
the immutable pre-adaptive image digest.

## External Risk

YouTube can change extraction and playback behavior without notice. The current
implementation handles the adaptive-live change verified on 2026-08-20, but no
YouTube integration can be guaranteed indefinitely. Future updates should retain
the same workflow: create a rollback point, pin and test yt-dlp, run live playback
probes, then deploy.
