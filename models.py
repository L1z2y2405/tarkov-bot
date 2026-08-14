from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Post:
    post_id: str
    post_url: str
    text: str
    published_at: datetime | None
    author: str
    images: tuple[str, ...] = field(default_factory=tuple)
    has_video: bool = False


@dataclass(frozen=True, slots=True)
class StoredState:
    last_post_id: str | None
