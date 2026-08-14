from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from models import Post


@dataclass(frozen=True, slots=True)
class BrowserConfig:
    user_agent: str
    locale: str
    timezone_id: str
    viewport_width: int
    viewport_height: int


class TwitterClientError(RuntimeError):
    pass


class TwitterBrowserError(TwitterClientError):
    pass


class TwitterParseError(TwitterClientError):
    pass


class TwitterClient:
    def __init__(self, username: str, headless: bool, retry_attempts: int) -> None:
        self._username = username
        self._headless = headless
        self._retry_attempts = max(1, retry_attempts)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._browser_config = BrowserConfig(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
            viewport_width=1440,
            viewport_height=1600,
        )

    async def fetch_latest_post(self) -> Post:
        last_error: Exception | None = None
        for attempt in range(1, self._retry_attempts + 1):
            try:
                return await self._fetch_latest_post_once()
            except TwitterParseError:
                raise
            except (asyncio.TimeoutError, OSError, TwitterBrowserError) as exc:
                last_error = exc
                self._logger.warning(
                    "Browser/network attempt %s/%s failed: %s",
                    attempt,
                    self._retry_attempts,
                    exc,
                )
                if attempt < self._retry_attempts:
                    await asyncio.sleep(2 * attempt)
            except Exception:
                self._logger.exception("Unexpected failure while fetching post")
                raise

        assert last_error is not None
        raise TwitterBrowserError("Failed to fetch latest post") from last_error

    async def _fetch_latest_post_once(self) -> Post:
        self._logger.info("Opening X profile...")
        try:
            from playwright.async_api import async_playwright
            from playwright.async_api import expect
        except ImportError as exc:  # pragma: no cover
            raise TwitterBrowserError("playwright is required") from exc

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self._headless)
                context = await browser.new_context(
                    user_agent=self._browser_config.user_agent,
                    locale=self._browser_config.locale,
                    timezone_id=self._browser_config.timezone_id,
                    viewport={
                        "width": self._browser_config.viewport_width,
                        "height": self._browser_config.viewport_height,
                    },
                )
                await context.set_extra_http_headers(
                    {
                        "Accept-Language": self._browser_config.locale,
                    }
                )
                try:
                    page = await context.new_page()
                    try:
                        await page.goto(
                            f"https://x.com/{self._username}",
                            wait_until="domcontentloaded",
                            timeout=30000,
                        )
                        self._logger.info("Waiting for posts...")
                        latest_article = await self._select_latest_non_pinned_article(page)
                        await expect(latest_article).to_be_visible(timeout=30000)
                        post = await self._parse_latest_post(latest_article)
                        self._logger.info("Latest post detected: %s", post.post_id)
                        self._logger.info("Parsed successfully.")
                        return post
                    finally:
                        await page.close()
                finally:
                    try:
                        await context.close()
                    finally:
                        await browser.close()
        except TwitterParseError:
            raise
        except Exception as exc:
            raise TwitterBrowserError("Failed to load X profile") from exc

    async def _select_latest_non_pinned_article(self, page: Any) -> Any:
        articles = page.locator("article")
        count = await articles.count()
        if count == 0:
            raise TwitterBrowserError("No posts found on X profile")

        for index in range(count):
            article = articles.nth(index)
            if await self._is_pinned_post(article):
                continue
            return article

        raise TwitterBrowserError("Only pinned posts were found")

    async def _parse_latest_post(self, article: Any) -> Post:
        try:
            href = await self._extract_status_href(article)
            post_id = self._extract_post_id(href)
            post_url = self._normalize_url(href)
            text = await self._extract_text(article)
            published_at = await self._extract_published_at(article)
            images = await self._extract_images(article)
            has_video = await self._has_video(article)
            return Post(
                post_id=post_id,
                post_url=post_url,
                text=text,
                published_at=published_at,
                author=f"@{self._username}",
                images=images,
                has_video=has_video,
            )
        except TwitterParseError:
            self._logger.exception("Failed to parse latest post")
            raise
        except Exception as exc:
            self._logger.exception("Failed to parse latest post")
            raise TwitterParseError("Failed to parse latest post") from exc

    async def _extract_status_href(self, article: Any) -> str:
        link_locator = article.locator('a[href*="/status/"]').first
        if await link_locator.count() == 0:
            raise TwitterParseError("Could not locate status link")

        href = await link_locator.get_attribute("href")
        if not href:
            raise TwitterParseError("Status link does not contain href")
        return href

    async def _is_pinned_post(self, article: Any) -> bool:
        pinned_markers = [
            'span:has-text("Pinned")',
            'span:has-text("Pinned post")',
            '[data-testid="socialContext"]:has-text("Pinned")',
        ]
        for selector in pinned_markers:
            if await article.locator(selector).count() > 0:
                return True
        return False

    def _extract_post_id(self, href: str) -> str:
        match = re.search(r"/status/(\d+)", href)
        if match is None:
            raise TwitterParseError(f"Could not extract post ID from {href!r}")
        return match.group(1)

    def _normalize_url(self, href: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return f"https://x.com{href}"

    async def _extract_text(self, article: Any) -> str:
        text_locator = article.locator('[data-testid="tweetText"]').first
        if await text_locator.count() > 0:
            return self._normalize_text(await text_locator.inner_text())

        fallback_text = await article.inner_text()
        cleaned = self._normalize_text(fallback_text)
        if not cleaned:
            raise TwitterParseError("Tweet text is empty")
        return cleaned

    async def _extract_published_at(self, article: Any) -> datetime | None:
        time_locator = article.locator("time").first
        if await time_locator.count() == 0:
            return None

        raw_value = await time_locator.get_attribute("datetime")
        if not raw_value:
            return None

        try:
            parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TwitterParseError(
                f"Invalid publish time: {raw_value!r}"
            ) from exc
        return parsed.astimezone(timezone.utc)

    async def _extract_images(self, article: Any) -> tuple[str, ...]:
        images: list[str] = []
        media_selectors = [
            'div[data-testid="tweetPhoto"] img',
            'div[data-testid="videoPlayer"] video',
            'div[data-testid="videoComponent"] video',
        ]

        for selector in media_selectors:
            count = await article.locator(selector).count()
            for index in range(count):
                locator = article.locator(selector).nth(index)
                src = await locator.get_attribute("src")
                if not src:
                    src = await locator.get_attribute("poster")
                if not src:
                    continue
                if "pbs.twimg.com" not in src and "twimg.com" not in src:
                    continue
                if src not in images:
                    images.append(src)

        if images:
            return tuple(images)

        count = await article.locator("img").count()
        for index in range(count):
            locator = article.locator("img").nth(index)
            src = await locator.get_attribute("src")
            if not src:
                continue
            alt = (await locator.get_attribute("alt")) or ""
            if alt.lower() in {"", "image", "video thumbnail"}:
                pass
            if "profile_images" in src or "avatar" in src:
                continue
            if "pbs.twimg.com" not in src and "twimg.com" not in src:
                continue
            if src not in images:
                images.append(src)
        return tuple(images)

    async def _has_video(self, article: Any) -> bool:
        return await article.locator(
            '[data-testid="videoPlayer"], [data-testid="videoComponent"]'
        ).count() > 0

    def _normalize_text(self, text: str) -> str:
        lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = re.sub(
                r"(?i)\bshow more\b|\bshow less\b|\bshow\b",
                "",
                line,
            ).strip()
            if not line:
                continue
            if line.endswith("h") and line[:-1].isdigit():
                continue
            if re.fullmatch(r"[\d.,]+[KM]?", line):
                continue
            lines.append(line)

        cleaned = "\n".join(lines).strip()
        if cleaned.startswith("@"):
            cleaned = cleaned.split("\n", 1)[-1].strip()
        return cleaned
