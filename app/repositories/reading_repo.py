from __future__ import annotations

from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from ..utils import maybe_object_id, serialize_doc


class ReadingRepository:
    def __init__(self, db):
        self.collection = db.reading_list if db is not None else None

    def available(self) -> bool:
        return self.collection is not None

    def list_entries_page(self, page: int = 1, per_page: int = 24):
        if self.collection is None:
            return [], 0

        safe_page = max(page, 1)
        safe_per_page = max(per_page, 1)
        skip = (safe_page - 1) * safe_per_page

        total = self.collection.count_documents({})
        docs = self.collection.find({}).sort("created_at", DESCENDING).skip(skip).limit(safe_per_page)
        return [serialize_doc(doc) for doc in docs], total

    def list_entries(self, limit: int = 200):
        if self.collection is None:
            return []

        docs = self.collection.find({}).sort("created_at", DESCENDING).limit(limit)
        return [serialize_doc(doc) for doc in docs]

    def insert_entry(self, payload: dict):
        if self.collection is None:
            raise RuntimeError("Database unavailable")

        try:
            result = self.collection.insert_one(payload)
        except DuplicateKeyError as exc:
            raise ValueError("Book is already in reading list") from exc

        created = self.collection.find_one({"_id": result.inserted_id})
        return serialize_doc(created)

    def delete_entry(self, entry_id: str) -> bool:
        if self.collection is None:
            raise RuntimeError("Database unavailable")

        object_id = maybe_object_id(entry_id)
        if not object_id:
            return False

        result = self.collection.delete_one({"_id": object_id})
        return result.deleted_count > 0

    def count_by_book_id(self, book_id: str) -> int:
        if self.collection is None:
            return 0

        object_id = maybe_object_id(book_id)
        if not object_id:
            return 0

        return self.collection.count_documents({"book_id": object_id})

    def count_entries(self) -> int:
        if self.collection is None:
            return 0
        return self.collection.count_documents({})
