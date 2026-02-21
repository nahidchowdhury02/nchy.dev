from __future__ import annotations

from urllib.parse import urlparse

from ..repositories.github_research_repo import GithubResearchRepository
from .media_storage_service import delete_research_pdf, upload_research_pdf


class GithubResearchService:
    VALID_KINDS = {"repository", "research_pdf"}

    def __init__(self, db):
        self.repo = GithubResearchRepository(db)

    def list_public_repositories(self):
        if not self.repo.available():
            return []
        return [self._serialize_item(item) for item in self.repo.list_public_by_kind("repository")]

    def list_public_research_pdfs(self):
        if not self.repo.available():
            return []
        return [self._serialize_item(item) for item in self.repo.list_public_by_kind("research_pdf")]

    def list_admin_items(self):
        if not self.repo.available():
            return []
        return [self._serialize_item(item) for item in self.repo.list_admin()]

    def create_item(self, payload: dict, file_storage=None):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for GitHub and research management")
        item = self._validate_payload(payload, file_storage=file_storage)
        created = self.repo.insert_item(item)
        return self._serialize_item(created)

    def update_item(self, item_id: str, payload: dict, file_storage=None):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for GitHub and research management")
        current_item = self.repo.get_by_id(item_id)
        item = self._validate_payload(payload, file_storage=file_storage, current_item=current_item)
        updated = self.repo.update_item(item_id, item)
        old_public_id = (current_item or {}).get("storage_public_id", "")
        new_public_id = item.get("storage_public_id", old_public_id)
        if old_public_id and old_public_id != new_public_id:
            delete_research_pdf(old_public_id)
        return self._serialize_item(updated)

    def delete_item(self, item_id: str):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for GitHub and research management")
        current_item = self.repo.get_by_id(item_id)
        deleted = self.repo.delete_item(item_id)
        if deleted:
            delete_research_pdf((current_item or {}).get("storage_public_id", ""))
        return deleted

    def count_items(self) -> int:
        if not self.repo.available():
            return 0
        return self.repo.count_items()

    def _validate_payload(self, payload: dict, file_storage=None, current_item: dict | None = None):
        kind = (payload.get("kind") or "").strip().lower()
        if kind not in self.VALID_KINDS:
            raise ValueError("Choose either Repository or Research PDF")

        title = (payload.get("title") or "").strip()
        if not title:
            raise ValueError("Title is required")

        url = (payload.get("url") or "").strip()
        source_filename = (current_item or {}).get("source_filename", "")
        storage_public_id = (current_item or {}).get("storage_public_id", "")

        if kind == "research_pdf":
            if file_storage and getattr(file_storage, "filename", ""):
                upload_result = upload_research_pdf(file_storage)
                url = upload_result["pdf_url"]
                source_filename = upload_result["filename"]
                storage_public_id = upload_result["public_id"]
                if not title:
                    title = upload_result["filename"]
        else:
            source_filename = ""
            storage_public_id = ""

        if not url or not (url.startswith("http://") or url.startswith("https://") or url.startswith("/")):
            raise ValueError("Provide a valid URL or upload a PDF file")

        description = (payload.get("description") or "").strip()
        try:
            sort_order = int(payload.get("sort_order") or 0)
        except (TypeError, ValueError):
            sort_order = 0
        is_published_raw = payload.get("is_published")
        is_published = str(is_published_raw).lower() in {"1", "true", "yes", "on"}

        return {
            "kind": kind,
            "title": title,
            "url": url,
            "description": description,
            "sort_order": sort_order,
            "is_published": is_published,
            "source_filename": source_filename,
            "storage_public_id": storage_public_id,
        }

    def _serialize_item(self, item: dict | None):
        if not item:
            return None
        payload = dict(item)
        is_repository = payload.get("kind") == "repository"
        payload["kind_label"] = "Repository" if is_repository else "Research PDF"
        payload["repo_path"] = ""
        payload["repo_preview_image"] = ""

        if is_repository:
            repo_path = self._extract_repo_path(payload.get("url", ""))
            payload["repo_path"] = repo_path
            if repo_path:
                payload["repo_preview_image"] = f"https://opengraph.githubassets.com/1/{repo_path}"

        return payload

    def _extract_repo_path(self, raw_url: str) -> str:
        try:
            parsed = urlparse((raw_url or "").strip())
        except ValueError:
            return ""

        host = (parsed.netloc or "").lower()
        if host not in {"github.com", "www.github.com"}:
            return ""

        parts = [part for part in (parsed.path or "").split("/") if part]
        if len(parts) < 2:
            return ""
        return f"{parts[0]}/{parts[1]}"
