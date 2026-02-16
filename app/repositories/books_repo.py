from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from ..utils import maybe_object_id, serialize_doc


class BooksRepository:
    def __init__(self, db):
        self.collection = db.books if db is not None else None

    def available(self) -> bool:
        return self.collection is not None

    def list_books(self, query: str = "", limit: int = 20, cursor: str | None = None):
        if not self.collection:
            return [], None

        filters: dict[str, Any] = {}
        if query:
            regex = {"$regex": query, "$options": "i"}
            filters["$or"] = [
                {"title": regex},
                {"original_title": regex},
                {"authors": regex},
            ]

        if cursor:
            cursor_id = maybe_object_id(cursor)
            if cursor_id:
                filters["_id"] = {"$gt": cursor_id}

        docs = list(self.collection.find(filters).sort("_id", ASCENDING).limit(limit + 1))
        next_cursor = None
        if len(docs) > limit:
            next_cursor = str(docs[limit - 1]["_id"])
            docs = docs[:limit]

        return [serialize_doc(doc) for doc in docs], next_cursor

    def list_previews(self, limit: int = 8):
        if not self.collection:
            return []

        docs = self.collection.find(
            {"cover_url": {"$nin": [None, ""]}},
            {"slug": 1, "title": 1, "original_title": 1, "cover_url": 1},
        ).sort("updated_at", DESCENDING).limit(limit)
        return [serialize_doc(doc) for doc in docs]

    def get_by_id_or_slug(self, id_or_slug: str):
        if not self.collection:
            return None

        filters: dict[str, Any]
        object_id = maybe_object_id(id_or_slug)
        if object_id:
            filters = {"_id": object_id}
        else:
            filters = {"slug": id_or_slug}

        doc = self.collection.find_one(filters)
        return serialize_doc(doc)

    def get_by_id(self, book_id: str):
        if not self.collection:
            return None
        object_id = maybe_object_id(book_id)
        if not object_id:
            return None
        doc = self.collection.find_one({"_id": object_id})
        return serialize_doc(doc)

    def update_book(self, book_id: str, update_fields: dict[str, Any]):
        if not self.collection:
            raise RuntimeError("Database unavailable")

        object_id = maybe_object_id(book_id)
        if not object_id:
            return None

        try:
            self.collection.update_one({"_id": object_id}, {"$set": update_fields})
        except DuplicateKeyError as exc:
            raise ValueError("Slug already exists") from exc
        return self.get_by_id(book_id)

    def upsert_by_original_title(self, original_title: str, payload: dict[str, Any]):
        if not self.collection:
            raise RuntimeError("Database unavailable")

        self.collection.update_one(
            {"original_title": original_title},
            {"$set": payload, "$setOnInsert": {"original_title": original_title}},
            upsert=True,
        )

    def count_books(self) -> int:
        if not self.collection:
            return 0
        return self.collection.count_documents({})
