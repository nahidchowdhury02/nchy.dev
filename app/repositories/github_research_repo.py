from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..utils import maybe_object_id, serialize_doc


class GithubResearchRepository:
    def __init__(self, db):
        self.collection = db.github_research_items if db is not None else None

    def available(self) -> bool:
        return self.collection is not None

    def list_public_by_kind(self, kind: str):
        if self.collection is None:
            return []
        docs = self.collection.find({"kind": kind, "is_published": True}).sort([("sort_order", 1), ("created_at", -1)])
        return [serialize_doc(doc) for doc in docs]

    def list_admin(self):
        if self.collection is None:
            return []
        docs = self.collection.find({}).sort([("kind", 1), ("sort_order", 1), ("created_at", -1)])
        return [serialize_doc(doc) for doc in docs]

    def insert_item(self, payload: dict[str, Any]):
        if self.collection is None:
            raise RuntimeError("Database unavailable")
        now = datetime.now(timezone.utc)
        payload["created_at"] = now
        payload["updated_at"] = now
        result = self.collection.insert_one(payload)
        return self.get_by_id(str(result.inserted_id))

    def update_item(self, item_id: str, payload: dict[str, Any]):
        if self.collection is None:
            raise RuntimeError("Database unavailable")
        object_id = maybe_object_id(item_id)
        if not object_id:
            return None
        payload["updated_at"] = datetime.now(timezone.utc)
        self.collection.update_one({"_id": object_id}, {"$set": payload})
        return self.get_by_id(item_id)

    def delete_item(self, item_id: str):
        if self.collection is None:
            raise RuntimeError("Database unavailable")
        object_id = maybe_object_id(item_id)
        if not object_id:
            return False
        result = self.collection.delete_one({"_id": object_id})
        return bool(result.deleted_count)

    def get_by_id(self, item_id: str):
        if self.collection is None:
            return None
        object_id = maybe_object_id(item_id)
        if not object_id:
            return None
        return serialize_doc(self.collection.find_one({"_id": object_id}))

    def count_items(self) -> int:
        if self.collection is None:
            return 0
        return self.collection.count_documents({})
