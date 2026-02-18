from __future__ import annotations

from datetime import datetime, timezone

from ..utils import serialize_doc


class SiteSettingsRepository:
    def __init__(self, db):
        self.collection = db.site_settings if db is not None else None

    def available(self) -> bool:
        return self.collection is not None

    def get_setting(self, key: str):
        if self.collection is None:
            return None
        return serialize_doc(self.collection.find_one({"key": key}))

    def upsert_setting(self, key: str, value: str):
        if self.collection is None:
            raise RuntimeError("Database unavailable")

        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"key": key},
            {
                "$set": {
                    "value": value,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "key": key,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        return self.get_setting(key)
