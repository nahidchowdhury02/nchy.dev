from __future__ import annotations

from ..utils import maybe_object_id, serialize_doc


class NotesRepository:
    def __init__(self, db):
        self.collection = db.notes_logs if db is not None else None

    def available(self) -> bool:
        return self.collection is not None

    def list_public(self, limit: int = 50, kind: str = "", sort_order: int = -1):
        if self.collection is None:
            return []
        query = {"is_published": True}
        normalized_kind = (kind or "").strip().lower()
        if normalized_kind in {"note", "log"}:
            query["kind"] = normalized_kind
        docs = self.collection.find(query).sort("created_at", sort_order).limit(limit)
        return [serialize_doc(doc) for doc in docs]

    def list_admin(self, limit: int = 200):
        if self.collection is None:
            return []
        docs = self.collection.find({}).sort("created_at", -1).limit(limit)
        return [serialize_doc(doc) for doc in docs]

    def insert_entry(self, payload: dict):
        if self.collection is None:
            raise RuntimeError("Database unavailable")
        result = self.collection.insert_one(payload)
        created = self.collection.find_one({"_id": result.inserted_id})
        return serialize_doc(created)

    def update_entry(self, entry_id: str, payload: dict):
        if self.collection is None:
            raise RuntimeError("Database unavailable")
        object_id = maybe_object_id(entry_id)
        if not object_id:
            return None
        self.collection.update_one({"_id": object_id}, {"$set": payload})
        return self.get_by_id(entry_id)

    def get_by_id(self, entry_id: str):
        if self.collection is None:
            return None
        object_id = maybe_object_id(entry_id)
        if not object_id:
            return None
        return serialize_doc(self.collection.find_one({"_id": object_id}))

    def count_entries(self) -> int:
        if self.collection is None:
            return 0
        return self.collection.count_documents({})

    def delete_entry(self, entry_id: str) -> bool:
        if self.collection is None:
            raise RuntimeError("Database unavailable")
        object_id = maybe_object_id(entry_id)
        if not object_id:
            return False
        result = self.collection.delete_one({"_id": object_id})
        return result.deleted_count > 0
