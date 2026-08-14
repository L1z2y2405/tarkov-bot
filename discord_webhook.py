from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib import error, request

from models import Post


class DiscordClient:
    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url

    def send_post(self, post: Post, logger: logging.Logger) -> None:
        if not self._webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL is not configured")

        payload = self._build_payload(post)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self._webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "tarkov-discord-notifier/0.1.0",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=30) as response:
                if response.status >= 400:
                    raise RuntimeError(f"Discord returned HTTP {response.status}")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace").strip()
            logger.error(
                "Discord webhook failed: HTTP %s %s%s",
                exc.code,
                exc.reason,
                f" | body: {body}" if body else "",
            )
            raise
        except (error.URLError, TimeoutError, RuntimeError) as exc:
            logger.error("Discord webhook failed: %s", exc)
            raise
        logger.info("Discord notification sent")

    def _build_payload(self, post: Post) -> dict[str, Any]:
        embed: dict[str, Any] = {
            "title": "New Escape from Tarkov Post",
            "description": post.text or "(no text)",
            "fields": [
                {"name": "Link", "value": post.post_url, "inline": False},
            ],
        }

        if post.images:
            embed["image"] = {"url": post.images[0]}

        return {"embeds": [embed]}
