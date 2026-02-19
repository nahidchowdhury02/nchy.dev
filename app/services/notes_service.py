from __future__ import annotations

from datetime import datetime, timezone

from ..repositories.notes_repo import NotesRepository
from .media_storage_service import delete_note_audio, upload_note_audio
from ..utils import parse_positive_int

VALID_KINDS = {"note", "log"}
VALID_EXTENSIONS = {".txt", ".md", ".log"}
MAX_UPLOAD_SIZE = 2 * 1024 * 1024


class NotesService:
    def __init__(self, db):
        self.repo = NotesRepository(db)

    def list_public_entries(self, limit_raw: str | None = None):
        limit = parse_positive_int(limit_raw, default=50, max_value=200)
        if not self.repo.available():
            return []
        return [self._serialize_entry(entry) for entry in self.repo.list_public(limit=limit)]

    def list_admin_entries(self, limit_raw: str | None = None):
        limit = parse_positive_int(limit_raw, default=200, max_value=500)
        if not self.repo.available():
            return []
        return [self._serialize_entry(entry) for entry in self.repo.list_admin(limit=limit)]

    def create_entry(self, form_data, file_storage=None, audio_file_storage=None):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for notes/log uploads")
        payload = self._validate_payload(
            form_data,
            file_storage=file_storage,
            audio_file_storage=audio_file_storage,
        )
        payload["created_at"] = datetime.now(timezone.utc)
        return self._serialize_entry(self.repo.insert_entry(payload))

    def update_entry(self, entry_id: str, form_data, file_storage=None, audio_file_storage=None):
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for notes/log uploads")

        current_entry = self.repo.get_by_id(entry_id)
        if not current_entry:
            return None

        payload = self._validate_payload(
            form_data,
            file_storage=file_storage,
            audio_file_storage=audio_file_storage,
            current_entry=current_entry,
        )
        payload["updated_at"] = datetime.now(timezone.utc)
        updated = self.repo.update_entry(entry_id, payload)
        old_audio_public_id = (current_entry or {}).get("audio_storage_public_id", "")
        new_audio_public_id = payload.get("audio_storage_public_id", old_audio_public_id)
        if old_audio_public_id and old_audio_public_id != new_audio_public_id:
            delete_note_audio(old_audio_public_id)
        return self._serialize_entry(updated)

    def remove_entry(self, entry_id: str) -> bool:
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for notes/log uploads")
        current_entry = self.repo.get_by_id(entry_id)
        deleted = self.repo.delete_entry(entry_id)
        if deleted:
            delete_note_audio((current_entry or {}).get("audio_storage_public_id", ""))
        return deleted

    def count_entries(self) -> int:
        if not self.repo.available():
            return 0
        return self.repo.count_entries()

    def _validate_payload(
        self,
        form_data,
        file_storage=None,
        audio_file_storage=None,
        current_entry: dict | None = None,
    ):
        kind = (form_data.get("kind") or "note").strip().lower()
        if kind not in VALID_KINDS:
            kind = "note"

        title = (form_data.get("title") or "").strip()
        body = (form_data.get("body") or "").strip()
        source_filename = (current_entry or {}).get("source_filename", "")
        audio_url = (current_entry or {}).get("audio_url", "")
        audio_storage_public_id = (current_entry or {}).get("audio_storage_public_id", "")
        audio_source_filename = (current_entry or {}).get("audio_source_filename", "")

        if file_storage and file_storage.filename:
            body = self._read_uploaded_text(file_storage)
            source_filename = file_storage.filename
            if not title:
                title = file_storage.filename

        if audio_file_storage and audio_file_storage.filename:
            upload_result = upload_note_audio(audio_file_storage)
            audio_url = upload_result["audio_url"]
            audio_storage_public_id = upload_result["public_id"]
            audio_source_filename = upload_result["filename"]
            if not title:
                title = upload_result["filename"]

        if not title:
            raise ValueError("Title is required")
        if not body and not audio_url:
            raise ValueError("Content is required (text, text file upload, or audio upload)")

        is_published = str(form_data.get("is_published", "")).lower() in {"1", "true", "yes", "on"}

        return {
            "kind": kind,
            "title": title,
            "body": body,
            "is_published": is_published,
            "source_filename": source_filename,
            "audio_url": audio_url,
            "audio_storage_public_id": audio_storage_public_id,
            "audio_source_filename": audio_source_filename,
        }

    def _read_uploaded_text(self, file_storage):
        filename = (file_storage.filename or "").lower()
        if not any(filename.endswith(ext) for ext in VALID_EXTENSIONS):
            raise ValueError("Only .txt, .md, and .log uploads are allowed")

        data = file_storage.read()
        if len(data) > MAX_UPLOAD_SIZE:
            raise ValueError("File is too large (max 2MB)")

        try:
            return data.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("Upload must be UTF-8 text") from exc

    def _serialize_entry(self, entry: dict | None):
        if not entry:
            return None
        payload = dict(entry)
        created = payload.get("created_at")
        if hasattr(created, "isoformat"):
            payload["created_at"] = created.isoformat()
        return payload
