from __future__ import annotations

from datetime import datetime, timezone

from ..utils import maybe_object_id, serialize_doc


class AdminRepository:
    def __init__(self, db):
        self.collection = db.admin_users if db is not None else None

    def available(self) -> bool:
        return self.collection is not None

    def get_by_username(self, username: str):
        if not self.collection:
            return None
        doc = self.collection.find_one({"username": username})
        return serialize_doc(doc)

    def get_by_id(self, user_id: str):
        if not self.collection:
            return None
        object_id = maybe_object_id(user_id)
        if not object_id:
            return None
        doc = self.collection.find_one({"_id": object_id})
        return serialize_doc(doc)

    def touch_last_login(self, username: str):
        if not self.collection:
            return
        self.collection.update_one(
            {"username": username},
            {"$set": {"last_login_at": datetime.now(timezone.utc)}},
        )

    def upsert_admin(self, username: str, password_hash: str):
        if not self.collection:
            raise RuntimeError("Database unavailable")

        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"username": username},
            {
                "$set": {
                    "password_hash": password_hash,
                    "is_active": True,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "created_at": now,
                },
            },
            upsert=True,
        )
        return self.get_by_username(username)
