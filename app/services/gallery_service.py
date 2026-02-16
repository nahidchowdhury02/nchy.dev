from __future__ import annotations

from datetime import datetime, timezone

from .cloudinary_service import delete_image, upload_image
from ..repositories.gallery_repo import GalleryRepository
from ..utils import parse_positive_int


VALID_CATEGORIES = {"sketches", "moments", "all"}
VALID_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class GalleryService:
    def __init__(self, db):
        self.repo = GalleryRepository(db)

    def list_public_items(self, category: str = "", limit_raw: str | None = None, cursor: str | None = None):
        limit = parse_positive_int(limit_raw, default=20, max_value=50)
        category = self._normalize_category(category)

        if not self.repo.available():
            return [], None

        items, next_cursor = self.repo.list_published(category=category, limit=limit, cursor=cursor)
        return [self._serialize_item(item) for item in items], next_cursor

    def list_admin_items(self, category: str = ""):
        category = self._normalize_category(category)
        if not self.repo.available():
            return []
        return [self._serialize_item(item) for item in self.repo.list_admin(category=category)]

    def create_item(self, payload: dict):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for gallery management")

        item = self._validate_payload(payload)
        now = datetime.now(timezone.utc)
        item["created_at"] = now
        item["updated_at"] = now
        created = self.repo.insert_item(item)
        return self._serialize_item(created)

    def update_item(self, item_id: str, payload: dict):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for gallery management")

        item = self._validate_payload(payload)
        item["updated_at"] = datetime.now(timezone.utc)
        updated = self.repo.update_item(item_id, item)
        return self._serialize_item(updated)

    def delete_item(self, item_id: str):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for gallery management")

        current_item = self.repo.get_by_id(item_id)
        deleted = self.repo.delete_item(item_id)
        if deleted and current_item:
            delete_image(current_item.get("cloudinary_public_id", ""))
        return deleted

    def upload_item_image(self, file_storage):
        if not file_storage:
            raise ValueError("Missing image file")

        if file_storage.mimetype not in VALID_MIME_TYPES:
            raise ValueError("Unsupported image format")

        upload_result = upload_image(file_storage)
        return {
            "image_url": upload_result["image_url"],
            "cloudinary_public_id": upload_result["public_id"],
        }

    def _validate_payload(self, payload: dict):
        category = self._normalize_category(payload.get("category", "all"))
        title = (payload.get("title") or "").strip() or "Untitled"
        caption = (payload.get("caption") or "").strip()
        image_url = (payload.get("image_url") or "").strip()
        cloudinary_public_id = (payload.get("cloudinary_public_id") or "").strip()

        try:
            sort_order = int(payload.get("sort_order") or 0)
        except (TypeError, ValueError):
            sort_order = 0

        is_published_raw = payload.get("is_published")
        is_published = str(is_published_raw).lower() in {"1", "true", "yes", "on"}

        return {
            "category": category,
            "title": title,
            "caption": caption,
            "image_url": image_url,
            "cloudinary_public_id": cloudinary_public_id,
            "sort_order": sort_order,
            "is_published": is_published,
        }

    def _normalize_category(self, category: str):
        normalized = (category or "").strip().lower()
        if normalized not in VALID_CATEGORIES:
            return "all"
        return normalized

    def _serialize_item(self, item: dict | None):
        if not item:
            return None
        payload = dict(item)
        for field in ("created_at", "updated_at"):
            value = payload.get(field)
            if hasattr(value, "isoformat"):
                payload[field] = value.isoformat()
        return payload
