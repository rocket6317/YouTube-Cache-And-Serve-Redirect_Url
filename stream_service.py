import logging

from db import (
    read_channel_configs,
    streams_table,
    update_stream,
    write_channels_file,
)
from fetcher import fetch_info, repair_live_info

logger = logging.getLogger("stream_service")


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
    config = current_channels.get(name, {})
    url = config.get("url") if isinstance(config, dict) else config
    url = url or stream.get("url")
    if not url:
        logger.warning(f"[REPAIR] No source URL configured for {name}")
        return False

    info = repair_live_info(
        url,
        name,
        known_channel_url=stream.get("channel_url"),
        known_channel_id=stream.get("channel_id"),
    )
    save_fetch_result(
        name,
        url,
        info,
        channels=current_channels,
        update_channels=True,
    )
    return bool(info.get("m3u8"))


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
    )
    save_fetch_result(
        name,
        url,
        repaired,
        channels=channels,
        update_channels=True,
    )
    return repaired
