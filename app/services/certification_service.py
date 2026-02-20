from __future__ import annotations

import re

from ..repositories.certification_repo import CertificationRepository


_UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class CertificationService:
    def __init__(self, db):
        self.repo = CertificationRepository(db)

    def list_public_badges(self):
        if not self.repo.available():
            return []
        return [self._serialize_badge(badge) for badge in self.repo.list_public()]

    def list_admin_badges(self):
        if not self.repo.available():
            return []
        return [self._serialize_badge(badge) for badge in self.repo.list_admin()]

    def create_badge(self, payload: dict):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for certification management")
        badge = self._validate_payload(payload)
        created = self.repo.insert_badge(badge)
        return self._serialize_badge(created)

    def update_badge(self, badge_id: str, payload: dict):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for certification management")
        badge = self._validate_payload(payload)
        updated = self.repo.update_badge(badge_id, badge)
        return self._serialize_badge(updated)

    def delete_badge(self, badge_id: str):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for certification management")
        return self.repo.delete_badge(badge_id)

    def count_badges(self) -> int:
        if not self.repo.available():
            return 0
        return self.repo.count_badges()

    def _validate_payload(self, payload: dict):
        credly_url = (payload.get("credly_url") or "").strip()
        badge_uuid = self._extract_badge_uuid(credly_url)
        if not badge_uuid:
            raise ValueError("Provide a valid Credly badge public URL")

        title = (payload.get("title") or "").strip()
        if not title:
            title = "Credly Badge"

        try:
            sort_order = int(payload.get("sort_order") or 0)
        except (TypeError, ValueError):
            sort_order = 0

        is_published_raw = payload.get("is_published")
        is_published = str(is_published_raw).lower() in {"1", "true", "yes", "on"}

        return {
            "title": title,
            "credly_url": credly_url,
            "badge_uuid": badge_uuid.lower(),
            "badge_host": "https://www.credly.com",
            "iframe_width": 150,
            "iframe_height": 270,
            "sort_order": sort_order,
            "is_published": is_published,
        }

    def _serialize_badge(self, badge: dict | None):
        if not badge:
            return None
        return dict(badge)

    def _extract_badge_uuid(self, url_or_text: str):
        value = (url_or_text or "").strip()
        if not value:
            return ""
        match = _UUID_PATTERN.search(value)
        if not match:
            return ""
        return match.group(0)
