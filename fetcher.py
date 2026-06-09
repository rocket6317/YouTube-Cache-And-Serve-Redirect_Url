import yt_dlp
import logging
import os
import re
from difflib import SequenceMatcher
from urllib.parse import urlparse, parse_qs
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# yt-dlp options – keep quiet and non-intrusive
ydl_opts = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "force_overwrites": False,
}


def _extract_info(url, channel_name=None, fatal=False):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        if fatal:
            raise
        print(
            f"[ERROR] Failed to fetch info for '{channel_name or url}' at {datetime.utcnow()} "
            f"Reason: {str(e)}"
        )
        return None


def _normalise_stream_info(info, source_url, channel_name=None, repaired=False):
    stream_url = info.get("url")
    if not stream_url:
        print(
            f"[ERROR] No stream URL found for '{channel_name or source_url}' at {datetime.utcnow()}"
        )
        return None

    return {
        "url": stream_url,
        "m3u8": stream_url,
        "channel": info.get("channel") or info.get("uploader"),
        "channel_url": info.get("channel_url") or info.get("uploader_url"),
        "channel_id": info.get("channel_id") or info.get("uploader_id"),
        "title": info.get("title"),
        "is_live": info.get("is_live"),
        "live_status": info.get("live_status"),
        "source_url": source_url,
        "resolved_live_url": source_url if repaired else None,
        "status": "ok",
        "last_error": None,
    }


def fetch_info(url, channel_name=None):
    """
    Safe wrapper around yt-dlp.
    Never raises to caller. Returns:
      - dict with stream info on success
      - None on failure
    """
    info = _extract_info(url, channel_name)
    if not info or not _is_currently_live(info):
        return None

    return _normalise_stream_info(info, url, channel_name)


def _read_metadata(url, channel_name=None):
    try:
        with yt_dlp.YoutubeDL(
            {**ydl_opts, "skip_download": True, "ignore_no_formats_error": True}
        ) as ydl:
            return ydl.extract_info(url, download=False) or {}
    except Exception as e:
        print(
            f"[ERROR] Could not read channel metadata for '{channel_name or url}' at "
            f"{datetime.utcnow()} Reason: {str(e)}"
        )
        return {}


def _extract_flat_playlist(url):
    try:
        with yt_dlp.YoutubeDL(
            {
                **ydl_opts,
                "extract_flat": True,
                "playlistend": 12,
            }
        ) as ydl:
            return ydl.extract_info(url, download=False) or {}
    except Exception:
        return {}


def _is_currently_live(info):
    return bool(info.get("is_live")) or info.get("live_status") == "is_live"


def _normalise_title(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _candidate_streams_urls(info, original_url, known_channel_url=None, known_channel_id=None):
    candidates = []

    def add(url):
        if url and url not in candidates:
            candidates.append(url)

    channel_url = known_channel_url or info.get("channel_url") or info.get("uploader_url")
    channel_id = known_channel_id or info.get("channel_id") or info.get("uploader_id")
    if channel_url:
        normalised_channel_url = channel_url.rstrip("/")
        for suffix in ("/streams", "/live", "/videos", "/featured"):
            if normalised_channel_url.endswith(suffix):
                normalised_channel_url = normalised_channel_url[: -len(suffix)]
                break
        add(normalised_channel_url + "/streams")
    if channel_id and str(channel_id).startswith("UC"):
        add(f"https://www.youtube.com/channel/{channel_id}/streams")

    parsed = urlparse(original_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    for part in path_parts:
        if part.startswith("@"):
            add(f"https://www.youtube.com/{part}/streams")
    return candidates


def _discover_live_candidates(
    metadata,
    original_url,
    channel_name=None,
    known_channel_url=None,
    known_channel_id=None,
):
    candidates = []
    seen_urls = set()
    for streams_url in _candidate_streams_urls(
        metadata,
        original_url,
        known_channel_url=known_channel_url,
        known_channel_id=known_channel_id,
    ):
        playlist = _extract_flat_playlist(streams_url)
        non_live_after_live = 0
        for entry in (playlist.get("entries") or [])[:12]:
            candidate_url = entry.get("webpage_url") or entry.get("url")
            if not candidate_url or candidate_url in seen_urls:
                continue
            if not str(candidate_url).startswith(("http://", "https://")):
                candidate_url = f"https://www.youtube.com/watch?v={candidate_url}"
            seen_urls.add(candidate_url)
            info = _extract_info(candidate_url, channel_name)
            if not info or not _is_currently_live(info):
                if candidates:
                    non_live_after_live += 1
                    if non_live_after_live >= 2:
                        break
                continue
            non_live_after_live = 0
            normalised = _normalise_stream_info(info, candidate_url, channel_name, repaired=True)
            if normalised:
                candidates.append(normalised)
            if len(candidates) >= 5:
                return candidates
        if candidates:
            return candidates
    return candidates


def _select_live_candidate(candidates, previous_title):
    if len(candidates) == 1:
        return candidates[0]
    expected = _normalise_title(previous_title)
    if not expected:
        return None
    scored = [
        (
            SequenceMatcher(None, expected, _normalise_title(candidate.get("title"))).ratio(),
            candidate,
        )
        for candidate in candidates
    ]
    scored.sort(key=lambda item: item[0])
    best_score, best = scored[-1]
    second_score = scored[-2][0] if len(scored) > 1 else 0
    if best_score >= 0.8 and best_score - second_score >= 0.15:
        return best
    return None


def _lightweight_candidates(candidates):
    return [
        {
            "url": candidate.get("source_url"),
            "title": candidate.get("title") or "Untitled live stream",
            "channel": candidate.get("channel"),
        }
        for candidate in candidates
    ]


def _candidate_live_urls(
    info,
    original_url,
    channel_name=None,
    known_channel_url=None,
    known_channel_id=None,
):
    candidates = []

    def add(url):
        if url and url not in candidates:
            candidates.append(url)

    channel_url = known_channel_url or info.get("channel_url") or info.get("uploader_url")
    channel_id = known_channel_id or info.get("channel_id") or info.get("uploader_id")
    channel_handle = info.get("channel") or info.get("uploader")

    if channel_url:
        normalised_channel_url = channel_url.rstrip("/")
        add(
            normalised_channel_url
            if normalised_channel_url.endswith("/live")
            else normalised_channel_url + "/live"
        )

    if channel_id:
        if str(channel_id).startswith("@"):
            add(f"https://www.youtube.com/{channel_id}/live")
        elif str(channel_id).startswith("UC"):
            add(f"https://www.youtube.com/channel/{channel_id}/live")

    parsed = urlparse(original_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    for part in path_parts:
        if part.startswith("@"):
            add(f"https://www.youtube.com/{part}/live")
        elif part in ("channel", "c", "user") and len(path_parts) > path_parts.index(part) + 1:
            add(f"https://www.youtube.com/{part}/{path_parts[path_parts.index(part) + 1]}/live")

    if channel_handle:
        handle = str(channel_handle).strip()
        if handle.startswith("@"):
            add(f"https://www.youtube.com/{handle}/live")

    if channel_name:
        fallback = str(channel_name).strip()
        if fallback and " " not in fallback:
            if fallback.startswith("@"):
                add(f"https://www.youtube.com/{fallback}/live")
            else:
                add(f"https://www.youtube.com/@{fallback}/live")
                add(f"https://www.youtube.com/c/{fallback}/live")
                add(f"https://www.youtube.com/user/{fallback}/live")

    return candidates


def repair_live_info(
    url,
    channel_name=None,
    known_channel_url=None,
    known_channel_id=None,
    known_title=None,
):
    """
    Find the current livestream for a saved YouTube URL.

    This is mainly for saved watch?v= links whose broadcast ID changes. It first
    tries the saved URL, then derives channel /live candidates from metadata.
    """
    metadata = _extract_info(url, channel_name)
    if metadata and _is_currently_live(metadata):
        direct = _normalise_stream_info(metadata, url, channel_name)
        if direct:
            direct["status"] = "ok"
            return direct

    if not metadata:
        metadata = _read_metadata(url, channel_name)

    live_candidates = _discover_live_candidates(
        metadata,
        url,
        channel_name,
        known_channel_url=known_channel_url,
        known_channel_id=known_channel_id,
    )
    selected = _select_live_candidate(live_candidates, known_title or metadata.get("title"))
    if selected:
        selected["status"] = "repaired"
        return selected
    if live_candidates:
        return {
            "url": None,
            "m3u8": None,
            "channel": metadata.get("channel") or metadata.get("uploader") or channel_name,
            "channel_url": known_channel_url or metadata.get("channel_url") or metadata.get("uploader_url"),
            "channel_id": known_channel_id or metadata.get("channel_id") or metadata.get("uploader_id"),
            "title": metadata.get("title"),
            "source_url": url,
            "resolved_live_url": None,
            "status": "selection_required",
            "last_error": "Multiple current live streams found; select one on the dashboard",
            "live_candidates": _lightweight_candidates(live_candidates),
        }

    for candidate in _candidate_live_urls(
        metadata,
        url,
        channel_name,
        known_channel_url=known_channel_url,
        known_channel_id=known_channel_id,
    ):
        print(f"[REPAIR] Trying live candidate for '{channel_name or url}': {candidate}")
        candidate_info = _extract_info(candidate, channel_name)
        if not candidate_info or not _is_currently_live(candidate_info):
            continue
        repaired = _normalise_stream_info(candidate_info, candidate, channel_name, repaired=True)
        if repaired:
            repaired["status"] = "repaired"
            return repaired

    return {
        "url": None,
        "m3u8": None,
        "channel": metadata.get("channel") or metadata.get("uploader") or channel_name,
        "channel_url": known_channel_url or metadata.get("channel_url") or metadata.get("uploader_url"),
        "channel_id": known_channel_id or metadata.get("channel_id") or metadata.get("uploader_id"),
        "title": metadata.get("title"),
        "source_url": url,
        "resolved_live_url": None,
        "status": "no_live_found",
        "last_error": "No current YouTube live stream found",
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
    # Read channels.txt
    try:
        with open("channels.txt") as f:
            urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Failed to read channels.txt: {e}")
        return

    for url in urls:
        name = extract_name(url)

        info = fetch_info(url, name)
        if info is None:
            logger.error(f"[ERROR] Skipping {url} — fetch failed")
            continue

        m3u8 = info["m3u8"]
        channel_name = info["channel"] or name

        from db import update_stream
        update_stream(name, url, m3u8, channel_name)
        logger.info(f"[CACHE] {channel_name} cached as {name}")

    # Save last update timestamp
    try:
        now_iso = datetime.utcnow().isoformat()
        timestamps_path = os.path.join(os.getenv("DATA_DIR", "."), "timestamps.txt")
        with open(timestamps_path, "w") as f:
            f.write(now_iso)
        logger.info(f"[TIMESTAMP] Updated at {now_iso}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to write timestamps.txt: {e}")
