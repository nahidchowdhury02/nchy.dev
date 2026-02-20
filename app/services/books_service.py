from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app

from ..repositories.books_repo import BooksRepository
from ..repositories.reading_repo import ReadingRepository
from ..utils import ensure_unique_slug, extract_year, parse_positive_int, slugify

_ISBN_PATTERN = re.compile(r"^[0-9Xx \-]+$")


class BooksService:
    def __init__(self, db):
        self.repo = BooksRepository(db)
        self.reading_repo = ReadingRepository(db)

    def list_public_books(self, query: str = "", limit_raw: str | None = None, cursor: str | None = None):
        limit = parse_positive_int(limit_raw, default=20, max_value=50)

        if not self.repo.available():
            return self._list_fallback_books(query=query, limit=limit, cursor=cursor)
        books, next_cursor = self.repo.list_books(query=query, limit=limit, cursor=cursor)
        return [self._to_public_payload(book) for book in books], next_cursor

    def list_public_books_page(self, query: str = "", page_raw: str | None = None, per_page_raw: str | None = None):
        page = parse_positive_int(page_raw, default=1, max_value=100000)
        per_page = parse_positive_int(per_page_raw, default=24, max_value=100)

        if not self.repo.available():
            all_books = self._search_fallback_books(query=query)
            total = len(all_books)
            total_pages = max(1, (total + per_page - 1) // per_page)
            safe_page = min(max(page, 1), total_pages)
            start = (safe_page - 1) * per_page
            end = start + per_page
            return {
                "items": [self._to_public_payload(book) for book in all_books[start:end]],
                "page": safe_page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_prev": safe_page > 1,
                "has_next": safe_page < total_pages,
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
            book = next(
                (
                    candidate
                    for candidate in self._fallback_books()
                    if candidate.get("slug") == id_or_slug or candidate.get("id") == id_or_slug
                ),
                None,
            )
            return self._to_public_payload(book)
        book = self.repo.get_by_id_or_slug(id_or_slug)
        return self._to_public_payload(book)

    def list_preview_books(self, limit: int = 8):
        if not self.repo.available():
            docs = [book for book in self._fallback_books() if book.get("cover_url")]
            docs = docs[: max(limit, 0)]
        else:
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

    def create_admin_book(self, form_data: dict[str, Any]):
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

        now = datetime.now(timezone.utc)
        created = self.repo.insert_book(
            {
                "slug": slug,
                "original_title": title,
                "title": title,
                "subtitle": subtitle,
                "authors": authors,
                "first_publish_year": first_publish_year,
                "cover_url": cover_url,
                "description": description,
                "google_info": None,
                "updated_at": now,
                "created_at": now,
            }
        )
        return self._to_admin_payload(created)

    def delete_admin_book(self, book_id: str) -> bool:
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for admin updates")

        reading_refs = self.reading_repo.count_by_book_id(book_id)
        if reading_refs > 0:
            raise ValueError("Remove this book from reading list before deleting")

        return self.repo.delete_book(book_id)

    def search_open_books(self, query: str, limit_raw: str | None = None):
        query_text = (query or "").strip()
        if not query_text:
            return []

        limit = parse_positive_int(limit_raw, default=8, max_value=20)
        api_base = (current_app.config.get("OPEN_BOOK_API_BASE_URL") or "https://openlibrary.org").strip().rstrip("/")
        api_key = (current_app.config.get("OPEN_BOOK_API_KEY") or "").strip()

        params = {"limit": limit}
        normalized_isbn = self._normalize_isbn(query_text)
        if normalized_isbn:
            params["isbn"] = normalized_isbn
        else:
            params["title"] = query_text

        if api_key:
            params["api_key"] = api_key

        request_headers = {
            "Accept": "application/json",
            "User-Agent": "nchydev-source/1.0",
        }
        if api_key:
            request_headers["Authorization"] = f"Bearer {api_key}"

        url = f"{api_base}/search.json?{urlencode(params)}"
        request = Request(url=url, headers=request_headers)
        try:
            with urlopen(request, timeout=8) as response:
                body = response.read().decode("utf-8")
        except (HTTPError, OSError, TimeoutError, URLError):
            return []

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return []

        docs = data.get("docs")
        if not isinstance(docs, list):
            return []

        results = []
        for doc in docs[:limit]:
            if not isinstance(doc, dict):
                continue
            normalized = self._to_open_book_result(doc)
            if normalized:
                results.append(normalized)
        return results

    def create_admin_book_from_open_result(self, form_data: dict[str, Any]):
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
        source_open_key = (form_data.get("source_open_key") or "").strip()
        source_isbn = self._normalize_isbn((form_data.get("source_isbn") or "").strip())

        base_slug = slugify((form_data.get("slug") or title).strip())
        slug = self._ensure_repo_unique_slug(base_slug)

        now = datetime.now(timezone.utc)
        created = self.repo.insert_book(
            {
                "slug": slug,
                "original_title": title,
                "title": title,
                "subtitle": subtitle,
                "authors": authors,
                "first_publish_year": first_publish_year,
                "cover_url": cover_url,
                "description": description,
                "google_info": None,
                "open_book_key": source_open_key or None,
                "isbn": source_isbn or None,
                "updated_at": now,
                "created_at": now,
            }
        )
        return self._to_admin_payload(created)

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
            return len(self._fallback_books())
        return self.repo.count_books()

    def _list_fallback_books(self, query: str, limit: int, cursor: str | None):
        books = self._search_fallback_books(query=query)
        offset = 0
        if cursor:
            try:
                offset = max(0, int(cursor))
            except ValueError:
                offset = 0

        page_slice = books[offset : offset + limit + 1]
        next_cursor = None
        if len(page_slice) > limit:
            next_cursor = str(offset + limit)
            page_slice = page_slice[:limit]

        return [self._to_public_payload(book) for book in page_slice], next_cursor

    def _search_fallback_books(self, query: str):
        books = self._fallback_books()
        query_text = (query or "").strip().lower()
        if not query_text:
            return books

        return [
            book
            for book in books
            if query_text in ((book.get("title") or "").lower())
            or query_text in ((book.get("original_title") or "").lower())
            or query_text in (" ".join(book.get("authors") or []).lower())
        ]

    @staticmethod
    @lru_cache(maxsize=1)
    def _fallback_books():
        base_dir = Path(__file__).resolve().parents[2]
        books_path = base_dir / "static" / "data" / "books.json"

        try:
            raw = json.loads(books_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(raw, list):
            return []

        service = BooksService(db=None)
        used_slugs: set[str] = set()
        normalized = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            doc = service.normalize_source_book(entry, used_slugs=used_slugs)
            doc["id"] = doc.get("slug")
            normalized.append(doc)
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

    def _to_open_book_result(self, doc: dict[str, Any]):
        title = (doc.get("title") or "").strip()
        if not title:
            return None

        subtitle = (doc.get("subtitle") or "").strip()

        authors_raw = doc.get("author_name")
        if isinstance(authors_raw, list):
            authors = [str(author).strip() for author in authors_raw if str(author).strip()]
        elif isinstance(authors_raw, str):
            authors = [authors_raw.strip()] if authors_raw.strip() else []
        else:
            authors = []

        first_publish_year = extract_year(doc.get("first_publish_year"))

        cover_id = doc.get("cover_i")
        cover_url = None
        if isinstance(cover_id, int):
            cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

        isbn_values = doc.get("isbn")
        source_isbn = ""
        if isinstance(isbn_values, list):
            for raw in isbn_values:
                normalized = self._normalize_isbn(str(raw))
                if normalized:
                    source_isbn = normalized
                    break

        source_open_key = (doc.get("key") or "").strip()

        return {
            "title": title,
            "subtitle": subtitle,
            "author": ", ".join(authors),
            "authors": authors,
            "first_publish_year": first_publish_year,
            "cover_url": cover_url,
            "description": "",
            "source_open_key": source_open_key,
            "source_isbn": source_isbn,
        }

    def _ensure_repo_unique_slug(self, base_slug: str) -> str:
        slug = base_slug or "untitled"
        if not self.repo.available():
            return slug

        candidate = slug
        suffix = 2
        while self.repo.get_by_slug(candidate):
            candidate = f"{slug}-{suffix}"
            suffix += 1
        return candidate

    def _normalize_isbn(self, value: str) -> str:
        candidate = (value or "").strip()
        if not candidate or not _ISBN_PATTERN.match(candidate):
            return ""

        compact = re.sub(r"[^0-9Xx]", "", candidate).upper()
        if len(compact) == 10:
            if compact[:-1].isdigit() and (compact[-1].isdigit() or compact[-1] == "X"):
                return compact
            return ""
        if len(compact) == 13 and compact.isdigit():
            return compact
        return ""
