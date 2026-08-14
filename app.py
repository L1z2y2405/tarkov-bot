from __future__ import annotations

import asyncio
import logging
from typing import NoReturn

from config import Settings
from discord_webhook import DiscordClient
from models import Post
from scheduler import NotifierScheduler
from storage import Storage
from twitter import TwitterClient


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


async def main() -> None:
    configure_logging()
    logger = logging.getLogger("tarkov-discord-notifier")
    logger.info("Starting notifier")

    settings = Settings.from_env()
    storage = Storage(settings.data_dir / "last_post.json")
    discord_client = DiscordClient(settings.discord_webhook_url)
    twitter_client = TwitterClient(
        username=settings.twitter_username,
        headless=settings.headless,
        retry_attempts=settings.retry_attempts,
    )

    scheduler = NotifierScheduler(
        twitter_client=twitter_client,
        discord_client=discord_client,
        storage=storage,
        check_interval_seconds=settings.check_interval_seconds,
        logger=logger,
    )
    if settings.run_once:
        await scheduler.check_once()
        logger.info("Run once complete. Shutting down.")
        return
    await scheduler.run()


def run() -> NoReturn:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger("tarkov-discord-notifier").info("Shutting down")
        raise SystemExit(0) from None


if __name__ == "__main__":
    run()
