from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..repositories.books_repo import BooksRepository
from ..repositories.reading_repo import ReadingRepository
from ..utils import maybe_object_id, parse_positive_int


class ReadingService:
    MAX_READING_NOTE_LENGTH = 280

    def __init__(self, db):
        self.repo = ReadingRepository(db)
        self.books_repo = BooksRepository(db)

    def list_public_books_page(self, page_raw: str | None = None, per_page_raw: str | None = None):
        page = parse_positive_int(page_raw, default=1, max_value=100000)
        per_page = parse_positive_int(per_page_raw, default=24, max_value=100)

        if not self.repo.available() or not self.books_repo.available():
            return self._empty_page(per_page=per_page)

        entries, total = self.repo.list_entries_page(page=page, per_page=per_page)
        total_pages = max(1, (total + per_page - 1) // per_page)

        if total > 0 and page > total_pages:
            page = total_pages
            entries, total = self.repo.list_entries_page(page=page, per_page=per_page)

        books_by_id = self._books_map(entries)
        items = []
        for entry in entries:
            book_id = entry.get("book_id")
            normalized_book_id = str(book_id) if book_id is not None else ""
            items.append(self._to_public_book_payload(books_by_id.get(normalized_book_id), entry=entry))
        items = [item for item in items if item]

        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        }

    def list_admin_entries(self, limit_raw: str | None = None):
        limit = parse_positive_int(limit_raw, default=200, max_value=500)

        if not self.repo.available() or not self.books_repo.available():
            return []

        entries = self.repo.list_entries(limit=limit)
        books_by_id = self._books_map(entries)
        return [self._to_admin_entry_payload(entry, books_by_id=books_by_id) for entry in entries]

    def add_book(self, book_id: str, reading_note: str = ""):
        if not self.repo.available() or not self.books_repo.available():
            raise RuntimeError("MongoDB is required for reading list updates")

        normalized_book_id = (book_id or "").strip()
        if not normalized_book_id:
            raise ValueError("Choose a book from library before adding")

        existing_book = self.books_repo.get_by_id(normalized_book_id)
        if not existing_book:
            raise ValueError("Book not found")
        object_id = maybe_object_id(existing_book["id"])
        if not object_id:
            raise ValueError("Book not found")

        now = datetime.now(timezone.utc)
        note = self._normalize_reading_note(reading_note)
        entry = self.repo.insert_entry(
            {
                "book_id": object_id,
                "reading_note": note,
                "created_at": now,
                "updated_at": now,
            }
        )

        return self._to_admin_entry_payload(
            entry,
            books_by_id={existing_book["id"]: existing_book},
        )

    def update_entry_note(self, entry_id: str, reading_note: str):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for reading list updates")

        payload = {
            "reading_note": self._normalize_reading_note(reading_note),
            "updated_at": datetime.now(timezone.utc),
        }
        return self.repo.update_entry(entry_id, payload)

    def remove_entry(self, entry_id: str) -> bool:
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for reading list updates")
        return self.repo.delete_entry(entry_id)

    def count_entries(self) -> int:
        if not self.repo.available():
            return 0
        return self.repo.count_entries()

    def _books_map(self, entries: list[dict[str, Any]]):
        seen: set[str] = set()
        book_ids: list[str] = []
        for entry in entries:
            book_id = entry.get("book_id")
            if book_id is None:
                continue
            normalized_book_id = str(book_id)
            if normalized_book_id in seen:
                continue
            seen.add(normalized_book_id)
            book_ids.append(normalized_book_id)

        books = self.books_repo.list_by_ids(book_ids)
        return {
            book.get("id"): book
            for book in books
            if isinstance(book, dict) and isinstance(book.get("id"), str)
        }

    def _to_public_book_payload(self, book: dict[str, Any] | None, entry: dict[str, Any] | None = None):
        if not book:
            return None

        updated_at = book.get("updated_at")
        if hasattr(updated_at, "isoformat"):
            updated_at = updated_at.isoformat()

        return {
            "id": book.get("id") or book.get("_id") or book.get("slug"),
            "slug": book.get("slug"),
            "original_title": book.get("original_title"),
            "title": book.get("title"),
            "subtitle": book.get("subtitle", ""),
            "authors": book.get("authors", []),
            "first_publish_year": book.get("first_publish_year"),
            "cover_url": book.get("cover_url"),
            "description": book.get("description", ""),
            "reading_note": (entry or {}).get("reading_note", ""),
            "updated_at": updated_at,
        }

    def _to_admin_book_payload(self, book: dict[str, Any] | None):
        if not book:
            return None
        authors = ", ".join(book.get("authors") or [])
        return {
            "id": book.get("id") or book.get("_id") or "",
            "title": book.get("title") or book.get("original_title") or "Untitled",
            "author": authors,
            "first_publish_year": book.get("first_publish_year"),
            "slug": book.get("slug") or "",
        }

    def _to_admin_entry_payload(self, entry: dict[str, Any], books_by_id: dict[str, dict[str, Any]]):
        created_at = entry.get("created_at")
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()

        book_id = entry.get("book_id")
        normalized_book_id = str(book_id) if book_id is not None else ""
        return {
            "id": entry.get("id"),
            "book_id": normalized_book_id,
            "reading_note": (entry.get("reading_note") or "").strip(),
            "created_at": created_at,
            "book": self._to_admin_book_payload(books_by_id.get(normalized_book_id)),
        }

    def _normalize_reading_note(self, note: str | None):
        value = (note or "").strip()
        if len(value) > self.MAX_READING_NOTE_LENGTH:
            raise ValueError(f"Reading note must be {self.MAX_READING_NOTE_LENGTH} characters or fewer")
        return value

    @staticmethod
    def _empty_page(per_page: int):
        return {
            "items": [],
            "page": 1,
            "per_page": per_page,
            "total": 0,
            "total_pages": 1,
            "has_prev": False,
            "has_next": False,
        }
