from __future__ import annotations

import logging
import asyncio

from discord_webhook import DiscordClient
from models import StoredState
from storage import Storage
from twitter import TwitterClient
from utils import retry_async


class NotifierScheduler:
    def __init__(
        self,
        twitter_client: TwitterClient,
        discord_client: DiscordClient,
        storage: Storage,
        check_interval_seconds: int,
        logger: logging.Logger,
    ) -> None:
        self._twitter_client = twitter_client
        self._discord_client = discord_client
        self._storage = storage
        self._check_interval_seconds = check_interval_seconds
        self._logger = logger

    async def run(self) -> None:
        while True:
            await self.check_once()
            await asyncio.sleep(self._check_interval_seconds)

    async def check_once(self) -> None:
        state = self._storage.load()
        try:
            post = await self._twitter_client.fetch_latest_post()
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Failed to fetch latest post: %s", exc)
            return

        if state.last_post_id == post.post_id:
            self._logger.info("No new post.")
            return

        self._logger.info("New post detected")

        try:
            await retry_async(
                lambda: asyncio.to_thread(
                    self._discord_client.send_post, post, self._logger
                ),
                3,
                self._logger,
            )
            self._storage.save(StoredState(last_post_id=post.post_id))
            self._logger.info("Updated last_post.json")
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Failed to process new post: %s", exc)
