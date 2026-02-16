from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..repositories.books_repo import BooksRepository
from ..utils import ensure_unique_slug, extract_year, parse_positive_int, slugify

BASE_DIR = Path(__file__).resolve().parents[2]
FALLBACK_BOOKS_FILE = BASE_DIR / "static" / "data" / "books.json"


class BooksService:
    def __init__(self, db):
        self.repo = BooksRepository(db)

    def list_public_books(self, query: str = "", limit_raw: str | None = None, cursor: str | None = None):
        limit = parse_positive_int(limit_raw, default=20, max_value=50)

        if self.repo.available():
            books, next_cursor = self.repo.list_books(query=query, limit=limit, cursor=cursor)
            return [self._to_public_payload(book) for book in books], next_cursor

        fallback_books = self._load_fallback_books()
        return self._list_fallback_books(fallback_books, query, limit, cursor)

    def get_public_book(self, id_or_slug: str):
        if self.repo.available():
            book = self.repo.get_by_id_or_slug(id_or_slug)
            return self._to_public_payload(book)

        for book in self._load_fallback_books():
            if book["slug"] == id_or_slug or book["id"] == id_or_slug:
                return self._to_public_payload(book)
        return None

    def list_preview_books(self, limit: int = 8):
        if self.repo.available():
            docs = self.repo.list_previews(limit=limit)
            return [self._to_preview_payload(doc) for doc in docs]

        previews = [
            self._to_preview_payload(book)
            for book in self._load_fallback_books()
            if book.get("cover_url")
        ]
        return previews[:limit]

    def list_admin_books(self, query: str = "", limit_raw: str | None = "100"):
        limit = parse_positive_int(limit_raw, default=100, max_value=200)

        if not self.repo.available():
            books = self._load_fallback_books()
            if query:
                lowered = query.lower()
                books = [book for book in books if lowered in book.get("title", "").lower()]
            return [self._to_admin_payload(book) for book in books[:limit]]

        docs, _ = self.repo.list_books(query=query, limit=limit)
        return [self._to_admin_payload(doc) for doc in docs]

    def get_admin_book(self, book_id: str):
        if not self.repo.available():
            return None

        doc = self.repo.get_by_id(book_id)
        return self._to_admin_payload(doc)

    def update_admin_book(self, book_id: str, form_data: dict[str, Any]):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for admin updates")

        title = (form_data.get("title") or "").strip()
        if not title:
            raise ValueError("Title is required")

        subtitle = (form_data.get("subtitle") or "").strip()
        author_input = (form_data.get("author") or "").strip()
        authors = [part.strip() for part in author_input.split(",") if part.strip()]

        year_raw = (form_data.get("first_publish_year") or "").strip()
        first_publish_year = extract_year(year_raw) if year_raw else None

        cover_url = (form_data.get("cover_url") or "").strip() or None
        description = (form_data.get("description") or "").strip()
        slug = slugify((form_data.get("slug") or title).strip())

        update_fields = {
            "title": title,
            "subtitle": subtitle,
            "authors": authors,
            "first_publish_year": first_publish_year,
            "cover_url": cover_url,
            "description": description,
            "slug": slug,
            "updated_at": datetime.now(timezone.utc),
        }

        updated = self.repo.update_book(book_id, update_fields)
        return self._to_admin_payload(updated)

    def normalize_source_book(self, raw_book: dict[str, Any], used_slugs: set[str] | None = None):
        if used_slugs is None:
            used_slugs = set()

        original_title = (raw_book.get("original_title") or "").strip()
        google_info = raw_book.get("google_info") if isinstance(raw_book.get("google_info"), dict) else None

        title = (google_info or {}).get("title") or original_title or "Untitled"
        subtitle = (google_info or {}).get("subtitle") or ""
        authors = (google_info or {}).get("authors") or []
        if isinstance(authors, str):
            authors = [authors]

        first_publish_year = extract_year((google_info or {}).get("publishedDate"))

        cover_url = raw_book.get("openlib_cover_url")
        if not cover_url or cover_url == "No cover available":
            cover_url = None

        description = (google_info or {}).get("description") or ""
        base_slug = slugify(original_title or title)
        slug = ensure_unique_slug(base_slug, used_slugs)

        now = datetime.now(timezone.utc)
        normalized = {
            "slug": slug,
            "original_title": original_title or title,
            "title": title,
            "subtitle": subtitle,
            "authors": authors,
            "first_publish_year": first_publish_year,
            "cover_url": cover_url,
            "description": description,
            "google_info": google_info,
            "updated_at": now,
            "created_at": now,
        }
        return normalized

    def _to_preview_payload(self, book: dict[str, Any] | None):
        if not book:
            return None
        return {
            "id": book.get("id") or book.get("_id") or book.get("slug"),
            "slug": book.get("slug"),
            "title": book.get("title") or book.get("original_title") or "Untitled",
            "cover_url": book.get("cover_url"),
        }

    def _to_public_payload(self, book: dict[str, Any] | None):
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
            "updated_at": updated_at,
        }

    def _to_admin_payload(self, book: dict[str, Any] | None):
        if not book:
            return None

        payload = self._to_public_payload(book)
        payload["author"] = ", ".join(payload.get("authors") or [])
        return payload

    def _load_fallback_books(self):
        if not FALLBACK_BOOKS_FILE.exists():
            return []

        with FALLBACK_BOOKS_FILE.open("r", encoding="utf-8") as handle:
            raw_books = json.load(handle)

        used_slugs: set[str] = set()
        normalized = []
        for raw_book in raw_books:
            book = self.normalize_source_book(raw_book, used_slugs=used_slugs)
            book["id"] = book["slug"]
            normalized.append(book)
        return normalized

    def _list_fallback_books(self, books, query: str, limit: int, cursor: str | None):
        if query:
            lowered = query.lower()
            books = [
                book
                for book in books
                if lowered in book.get("title", "").lower()
                or lowered in book.get("original_title", "").lower()
                or any(lowered in author.lower() for author in book.get("authors", []))
            ]

        start_index = 0
        if cursor:
            try:
                start_index = max(0, int(cursor))
            except ValueError:
                start_index = 0

        batch = books[start_index : start_index + limit]
        next_cursor = None
        if start_index + limit < len(books):
            next_cursor = str(start_index + limit)

        return [self._to_public_payload(book) for book in batch], next_cursor
