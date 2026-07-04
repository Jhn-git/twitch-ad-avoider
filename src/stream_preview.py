"""
Single-channel stream preview metadata and thumbnail fetching.

Uses the same public Twitch GraphQL endpoint as status_monitor.py, but fetches
richer per-channel data (title, preview thumbnail URL) for one channel at a
time rather than batched live/offline checks.
"""

from dataclasses import dataclass
from typing import Optional

import requests

from src.exceptions import ValidationError
from src.logging_config import get_logger
from src.validators import validate_channel_name

logger = get_logger(__name__)

_GQL_URL = "https://gql.twitch.tv/gql"
# Public client ID embedded in the Twitch website — used by streamlink and
# other open-source Twitch clients for anonymous GQL queries.
_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"


@dataclass
class StreamPreviewInfo:
    """Result of a single-channel stream preview lookup."""

    channel: str
    is_live: bool
    title: Optional[str] = None
    preview_image_url: Optional[str] = None


def fetch_stream_preview_info(channel: str, timeout: int = 10) -> StreamPreviewInfo:
    """
    Fetch stream title and preview thumbnail URL for a single channel.

    Never raises — any validation, network, or parsing failure degrades to an
    offline result so callers can treat this as a best-effort lookup.

    Args:
        channel: Twitch channel name
        timeout: Request timeout in seconds

    Returns:
        StreamPreviewInfo describing whether the channel is live and, if so,
        its title and preview image URL.
    """
    try:
        validated_channel = validate_channel_name(channel)
    except ValidationError as e:
        logger.warning(f"Skipping preview fetch for invalid channel {channel!r}: {e}")
        return StreamPreviewInfo(channel=channel, is_live=False)

    # Requested at a larger-than-default size (still 16:9) so the preview stays
    # sharp when the GUI scales it up to fill a wide panel.
    query = (
        "{ user(login: \"%s\") { stream { title previewImageURL(width: 640, height: 360) } } }"
        % validated_channel
    )

    try:
        response = requests.post(
            _GQL_URL,
            json={"query": query},
            headers={"Client-ID": _CLIENT_ID},
            timeout=timeout,
        )
        response.raise_for_status()

        data = response.json().get("data") or {}
        user_node = data.get("user") or {}
        stream_node = user_node.get("stream")

        if not stream_node:
            return StreamPreviewInfo(channel=validated_channel, is_live=False)

        return StreamPreviewInfo(
            channel=validated_channel,
            is_live=True,
            title=stream_node.get("title"),
            preview_image_url=stream_node.get("previewImageURL"),
        )
    except Exception as e:
        logger.warning(f"Failed to fetch stream preview for {validated_channel}: {e}")
        return StreamPreviewInfo(channel=validated_channel, is_live=False)


def fetch_image_bytes(url: str, timeout: int = 10) -> Optional[bytes]:
    """
    Download raw image bytes from a URL.

    Args:
        url: Image URL to download
        timeout: Request timeout in seconds

    Returns:
        Raw image bytes, or None on any failure.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.warning(f"Failed to fetch preview image from {url}: {e}")
        return None
