from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

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
        self._repo_root = Path(__file__).resolve().parent

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
            await self._persist_state_to_git()
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Failed to process new post: %s", exc)

    async def _persist_state_to_git(self) -> None:
        if not self._is_git_repo():
            self._logger.info("Git repository not available; skipping state push")
            return

        await asyncio.to_thread(self._git_commit_and_push)

    def _is_git_repo(self) -> bool:
        return (self._repo_root / ".git").exists()

    def _git_commit_and_push(self) -> None:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/last_post.json"],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if not status.stdout.strip():
            self._logger.info("No git changes to persist")
            return

        subprocess.run(
            ["git", "add", "data/last_post.json"],
            cwd=self._repo_root,
            check=True,
        )
        commit = subprocess.run(
            ["git", "commit", "-m", "Update last processed post"],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if commit.returncode != 0:
            if "nothing to commit" in commit.stderr.lower():
                self._logger.info("No git commit needed")
                return
            raise RuntimeError(commit.stderr.strip() or "git commit failed")

        push = subprocess.run(
            ["git", "push"],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if push.returncode != 0:
            raise RuntimeError(push.stderr.strip() or "git push failed")
        self._logger.info("Persisted last_post.json to git")
