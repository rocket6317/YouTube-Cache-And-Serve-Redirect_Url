import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

from db import (
    read_channel_configs,
    streams_table,
    update_stream,
    write_channels_file,
)
from fetcher import fetch_info, repair_live_info
from adaptive_hls import adaptive_stream_is_ready

logger = logging.getLogger("stream_service")


def _stream_config(channels, name):
    config = channels.get(name, {}) if channels else {}
    return config if isinstance(config, dict) else {"url": config}


def _use_fallback_if_offline(name, source_url, info, channels):
    config = _stream_config(channels, name)
    fallback_url = config.get("fallback_url")
    if info.get("status") != "no_live_found" or not fallback_url:
        return info
    return {
        **info,
        "url": fallback_url,
        "m3u8": fallback_url,
        "source_url": source_url,
        "status": "fallback",
        "stream_mode": "legacy",
        "last_error": "No current YouTube live stream found; using configured fallback",
    }


def cached_youtube_stream_is_stale(stream, interval_hours, now=None):
    m3u8 = (
        stream.get("video_m3u8")
        if stream.get("stream_mode") == "adaptive"
        else stream.get("m3u8")
    ) or ""
    try:
        host = (urlparse(m3u8).hostname or "").lower()
    except ValueError:
        return False
    if host != "googlevideo.com" and not host.endswith(".googlevideo.com"):
        return False
    try:
        last_success = datetime.fromisoformat(stream.get("last_success", ""))
    except (TypeError, ValueError):
        return True
    return last_success + timedelta(hours=interval_hours) <= (now or datetime.utcnow())


def save_fetch_result(name, original_url, info, channels=None, update_channels=False):
    new_url = info.get("source_url") or info.get("resolved_live_url") or original_url
    update_stream(
        name,
        new_url,
        info.get("m3u8"),
        info.get("channel") or name,
        status=info.get("status"),
        last_error=info.get("last_error"),
        resolved_live_url=info.get("resolved_live_url"),
        channel_url=info.get("channel_url"),
        channel_id=info.get("channel_id"),
        title=info.get("title"),
        live_candidates=info.get("live_candidates"),
        stream_mode=info.get("stream_mode"),
        video_m3u8=info.get("video_m3u8"),
        audio_m3u8=info.get("audio_m3u8"),
        video_codec=info.get("video_codec"),
        audio_codec=info.get("audio_codec"),
        video_width=info.get("video_width"),
        video_height=info.get("video_height"),
        video_fps=info.get("video_fps"),
        bandwidth=info.get("bandwidth"),
    )
    if update_channels and new_url != original_url:
        current_channels = channels if channels is not None else read_channel_configs()
        config = current_channels.get(name, {})
        if not isinstance(config, dict):
            config = {"url": config, "refresh_hours": None}
        config["url"] = new_url
        current_channels[name] = config
        write_channels_file(current_channels)
    return new_url


def repair_stream(name, channels=None):
    current_channels = channels if channels is not None else read_channel_configs()
    stream = streams_table().get(name, {})
    config = _stream_config(current_channels, name)
    url = config.get("url")
    url = url or stream.get("url")
    if not url:
        logger.warning(f"[REPAIR] No source URL configured for {name}")
        return False

    info = repair_live_info(
        url,
        name,
        known_channel_url=stream.get("channel_url"),
        known_channel_id=stream.get("channel_id"),
        known_title=stream.get("title"),
    )
    info = _use_fallback_if_offline(name, url, info, current_channels)
    save_fetch_result(
        name,
        url,
        info,
        channels=current_channels,
        update_channels=info.get("status") != "fallback",
    )
    return bool(info.get("m3u8") or adaptive_stream_is_ready(info))


def refresh_stream(name, url, channels=None, existing=None):
    info = fetch_info(url, name)
    if info:
        save_fetch_result(name, url, info)
        return info

    stream = existing if existing is not None else streams_table().get(name, {})
    repaired = repair_live_info(
        url,
        name,
        known_channel_url=stream.get("channel_url"),
        known_channel_id=stream.get("channel_id"),
        known_title=stream.get("title"),
    )
    repaired = _use_fallback_if_offline(name, url, repaired, channels)
    save_fetch_result(
        name,
        url,
        repaired,
        channels=channels,
        update_channels=repaired.get("status") != "fallback",
    )
    return repaired
