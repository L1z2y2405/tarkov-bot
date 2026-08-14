from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from models import StoredState


class Storage:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> StoredState:
        if not self._path.exists():
            return StoredState(last_post_id=None)

        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return StoredState(last_post_id=None)

        last_post_id = payload.get("last_post_id")
        if last_post_id is not None and not isinstance(last_post_id, str):
            return StoredState(last_post_id=None)
        return StoredState(last_post_id=last_post_id)

    def save(self, state: StoredState) -> None:
        payload = asdict(state)
        payload = {"last_post_id": payload["last_post_id"]}
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, indent=4, ensure_ascii=True), encoding="utf-8"
        )
        temp_path.replace(self._path)
