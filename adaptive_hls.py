from urllib.request import Request, urlopen

import m3u8


HTTP_TIMEOUT_SECONDS = 10
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
LIVE_WINDOW_SEGMENTS = 12


def adaptive_stream_is_ready(stream):
    return bool(
        stream.get("stream_mode") == "adaptive"
        and stream.get("video_m3u8")
        and stream.get("audio_m3u8")
    )


def build_master_playlist(stream, video_uri, audio_uri):
    width = int(stream.get("video_width") or 1920)
    height = int(stream.get("video_height") or 1080)
    fps = float(stream.get("video_fps") or 30)
    bandwidth = max(int(stream.get("bandwidth") or 6_000_000), 1)
    video_codec = stream.get("video_codec") or "avc1.640028"
    audio_codec = stream.get("audio_codec") or "mp4a.40.2"
    return "\n".join(
        [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            (
                '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Audio",'
                f'DEFAULT=YES,AUTOSELECT=YES,URI="{audio_uri}"'
            ),
            (
                f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={width}x{height},'
                f'FRAME-RATE={fps:.3f},CODECS="{video_codec},{audio_codec}",AUDIO="audio"'
            ),
            video_uri,
            "",
        ]
    )


def load_media_playlist(url, segment_limit=LIVE_WINDOW_SEGMENTS):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
        body = response.read(MAX_MANIFEST_BYTES + 1)
    if len(body) > MAX_MANIFEST_BYTES:
        raise ValueError("Upstream HLS playlist is too large")

    text = body.decode("utf-8", errors="replace")
    if not text.lstrip().startswith("#EXTM3U"):
        raise ValueError("Upstream response is not an HLS playlist")

    playlist = m3u8.loads(text, uri=url)
    if playlist.is_variant or not playlist.segments:
        raise ValueError("Expected an HLS media playlist")

    if len(playlist.segments) > segment_limit:
        removed = list(playlist.segments[:-segment_limit])
        kept = list(playlist.segments[-segment_limit:])
        playlist.media_sequence = (playlist.media_sequence or 0) + len(removed)
        playlist.discontinuity_sequence = (
            (playlist.discontinuity_sequence or 0)
            + sum(1 for segment in removed if segment.discontinuity)
        )
        first = kept[0]
        if first.program_date_time is None and first.current_program_date_time is not None:
            first.program_date_time = first.current_program_date_time
        playlist.segments = m3u8.SegmentList(kept)

    return playlist.dumps()
