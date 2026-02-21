from __future__ import annotations

import re

from ..repositories.music_repo import MusicRepository


_YOUTUBE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


class MusicService:
    def __init__(self, db):
        self.repo = MusicRepository(db)

    def list_public_links(self, sort: str = "newest"):
        if not self.repo.available():
            return []
        normalized_sort = (sort or "").strip().lower()
        if normalized_sort not in {"newest", "oldest"}:
            normalized_sort = "newest"
        return [self._serialize_link(link) for link in self.repo.list_public(sort=normalized_sort)]

    def list_admin_links(self):
        if not self.repo.available():
            return []
        return [self._serialize_link(link) for link in self.repo.list_admin()]

    def create_link(self, payload: dict):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for music management")
        link = self._validate_payload(payload)
        created = self.repo.insert_link(link)
        return self._serialize_link(created)

    def update_link(self, link_id: str, payload: dict):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for music management")
        link = self._validate_payload(payload)
        updated = self.repo.update_link(link_id, link)
        return self._serialize_link(updated)

    def delete_link(self, link_id: str):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for music management")
        return self.repo.delete_link(link_id)

    def count_links(self) -> int:
        if not self.repo.available():
            return 0
        return self.repo.count_links()

    def _validate_payload(self, payload: dict):
        title = (payload.get("title") or "").strip() or "Untitled"
        youtube_url = (payload.get("youtube_url") or "").strip()
        youtube_id = self._extract_youtube_id(youtube_url)
        if not youtube_id:
            raise ValueError("Provide a valid YouTube URL")

        try:
            sort_order = int(payload.get("sort_order") or 0)
        except (TypeError, ValueError):
            sort_order = 0

        is_published_raw = payload.get("is_published")
        is_published = str(is_published_raw).lower() in {"1", "true", "yes", "on"}

        return {
            "title": title,
            "youtube_url": youtube_url,
            "youtube_id": youtube_id,
            "sort_order": sort_order,
            "is_published": is_published,
        }

    def _serialize_link(self, link: dict | None):
        if not link:
            return None
        payload = dict(link)
        youtube_id = (payload.get("youtube_id") or "").strip()
        payload["embed_url"] = f"https://www.youtube.com/embed/{youtube_id}" if youtube_id else ""
        return payload

    def _extract_youtube_id(self, url_or_id: str):
        value = (url_or_id or "").strip()
        if not value:
            return ""

        if _YOUTUBE_ID_PATTERN.match(value):
            return value

        patterns = [
            r"(?:youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})",
            r"(?:youtube\.com/embed/)([A-Za-z0-9_-]{11})",
            r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, value)
            if match:
                return match.group(1)
        return ""
