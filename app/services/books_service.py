from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..repositories.books_repo import BooksRepository
from ..utils import ensure_unique_slug, extract_year, parse_positive_int, slugify


class BooksService:
    def __init__(self, db):
        self.repo = BooksRepository(db)

    def list_public_books(self, query: str = "", limit_raw: str | None = None, cursor: str | None = None):
        limit = parse_positive_int(limit_raw, default=20, max_value=50)

        if not self.repo.available():
            return [], None
        books, next_cursor = self.repo.list_books(query=query, limit=limit, cursor=cursor)
        return [self._to_public_payload(book) for book in books], next_cursor

    def list_public_books_page(self, query: str = "", page_raw: str | None = None, per_page_raw: str | None = None):
        page = parse_positive_int(page_raw, default=1, max_value=100000)
        per_page = parse_positive_int(per_page_raw, default=24, max_value=100)

        if not self.repo.available():
            return {
                "items": [],
                "page": 1,
                "per_page": per_page,
                "total": 0,
                "total_pages": 1,
                "has_prev": False,
                "has_next": False,
            }

        books, total = self.repo.list_books_page(query=query, page=page, per_page=per_page)
        total_pages = max(1, (total + per_page - 1) // per_page)

        # If page is out of range, clamp to the last available page.
        if total > 0 and page > total_pages:
            page = total_pages
            books, total = self.repo.list_books_page(query=query, page=page, per_page=per_page)

        return {
            "items": [self._to_public_payload(book) for book in books],
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
        }

    def get_public_book(self, id_or_slug: str):
        if not self.repo.available():
            return None
        book = self.repo.get_by_id_or_slug(id_or_slug)
        return self._to_public_payload(book)

    def list_preview_books(self, limit: int = 8):
        if not self.repo.available():
            return []
        docs = self.repo.list_previews(limit=limit)
        return [self._to_preview_payload(doc) for doc in docs]

    def list_admin_books(self, query: str = "", limit_raw: str | None = "100"):
        limit = parse_positive_int(limit_raw, default=100, max_value=200)

        if not self.repo.available():
            return []

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

    def count_books(self) -> int:
        if not self.repo.available():
            return 0
        return self.repo.count_books()

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
