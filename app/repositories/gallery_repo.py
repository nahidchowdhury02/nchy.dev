from __future__ import annotations

from typing import Any

from ..utils import maybe_object_id, serialize_doc


class GalleryRepository:
    def __init__(self, db):
        self.collection = db.gallery_items if db is not None else None

    def available(self) -> bool:
        return self.collection is not None

    def list_published(self, category: str = "", limit: int = 20, cursor: str | None = None):
        if not self.collection:
            return [], None

        filters: dict[str, Any] = {"is_published": True}
        if category and category != "all":
            filters["category"] = category

        if cursor:
            object_id = maybe_object_id(cursor)
            if object_id:
                filters["_id"] = {"$gt": object_id}

        docs = list(self.collection.find(filters).sort("_id", 1).limit(limit + 1))

        next_cursor = None
        if len(docs) > limit:
            next_cursor = str(docs[limit - 1]["_id"])
            docs = docs[:limit]

        return [serialize_doc(doc) for doc in docs], next_cursor

    def list_admin(self, category: str = ""):
        if not self.collection:
            return []

        filters: dict[str, Any] = {}
        if category and category != "all":
            filters["category"] = category

        docs = self.collection.find(filters).sort([("category", 1), ("sort_order", 1), ("created_at", -1)])
        return [serialize_doc(doc) for doc in docs]

    def get_by_id(self, item_id: str):
        if not self.collection:
            return None
        object_id = maybe_object_id(item_id)
        if not object_id:
            return None
        doc = self.collection.find_one({"_id": object_id})
        return serialize_doc(doc)

    def insert_item(self, payload: dict[str, Any]):
        if not self.collection:
            raise RuntimeError("Database unavailable")
        result = self.collection.insert_one(payload)
        return self.get_by_id(str(result.inserted_id))

    def update_item(self, item_id: str, payload: dict[str, Any]):
        if not self.collection:
            raise RuntimeError("Database unavailable")
        object_id = maybe_object_id(item_id)
        if not object_id:
            return None
        self.collection.update_one({"_id": object_id}, {"$set": payload})
        return self.get_by_id(item_id)

    def delete_item(self, item_id: str):
        if not self.collection:
            raise RuntimeError("Database unavailable")
        object_id = maybe_object_id(item_id)
        if not object_id:
            return False
        result = self.collection.delete_one({"_id": object_id})
        return bool(result.deleted_count)
