"""Slack outbound helpers + slash-command signature verification.

The /on slash command is the day-one input surface (emoji-react via n8n is the
other; Portal button comes later). Signature verification follows Slack's v0 scheme.
"""
from __future__ import annotations

import hashlib
import hmac
import time

import httpx

from .config import settings

_API = "https://slack.com/api"


def verify_signature(timestamp: str, signature: str, raw_body: bytes) -> bool:
    """Validate an incoming Slack request. Rejects stale (>5 min) timestamps."""
    if not settings.slack_signing_secret:
        # Dev convenience: with no secret configured, skip verification.
        return True
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except (TypeError, ValueError):
        return False
    basestring = f"v0:{timestamp}:{raw_body.decode()}".encode()
    digest = hmac.new(settings.slack_signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"v0={digest}", signature or "")


async def post_message(channel: str, text: str, blocks: list | None = None) -> None:
    if not settings.slack_bot_token:
        return  # no-op in dev
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"{_API}/chat.postMessage",
            headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
            json={"channel": channel, "text": text, **({"blocks": blocks} if blocks else {})},
        )
