from __future__ import annotations

from ..utils import serialize_doc


class NotesRepository:
    def __init__(self, db):
        self.collection = db.notes_logs if db is not None else None

    def available(self) -> bool:
        return self.collection is not None

    def list_public(self, limit: int = 50):
        if not self.collection:
            return []
        docs = self.collection.find({"is_published": True}).sort("created_at", -1).limit(limit)
        return [serialize_doc(doc) for doc in docs]

    def list_admin(self, limit: int = 200):
        if not self.collection:
            return []
        docs = self.collection.find({}).sort("created_at", -1).limit(limit)
        return [serialize_doc(doc) for doc in docs]

    def insert_entry(self, payload: dict):
        if not self.collection:
            raise RuntimeError("Database unavailable")
        result = self.collection.insert_one(payload)
        created = self.collection.find_one({"_id": result.inserted_id})
        return serialize_doc(created)

    def count_entries(self) -> int:
        if not self.collection:
            return 0
        return self.collection.count_documents({})
