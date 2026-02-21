from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from bson.binary import Binary
from flask import current_app, url_for
from werkzeug.utils import secure_filename

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".webm"}
MAX_AUDIO_UPLOAD_SIZE = 20 * 1024 * 1024
ALLOWED_PDF_EXTENSIONS = {".pdf"}
MAX_PDF_UPLOAD_SIZE = 25 * 1024 * 1024


def configure_media_storage(app):
    app.logger.info("Media storage backend: MongoDB")


def upload_image(file_storage):
    db = current_app.extensions.get("mongo_db")
    if db is None:
        raise RuntimeError("MongoDB is unavailable for upload storage")

    original_name = secure_filename(file_storage.filename or "")
    suffix = Path(original_name).suffix.lower() or ".bin"
    filename = original_name or f"{uuid4().hex}{suffix}"

    file_storage.stream.seek(0)
    content = file_storage.stream.read()
    result = db.gallery_upload_blobs.insert_one(
        {
            "filename": filename,
            "content_type": file_storage.mimetype or "application/octet-stream",
            "data": Binary(content),
        }
    )
    file_id = result.inserted_id

    return {
        "image_url": url_for("main.gallery_media", media_id=str(file_id), filename=filename),
        "public_id": f"mongo:{file_id}",
    }


def delete_image(public_id: str):
    if not public_id or not public_id.startswith("mongo:"):
        return

    object_id_raw = public_id.removeprefix("mongo:").strip()
    if not ObjectId.is_valid(object_id_raw):
        return

    db = current_app.extensions.get("mongo_db")
    if db is None:
        return

    db.gallery_upload_blobs.delete_one({"_id": ObjectId(object_id_raw)})


def upload_note_audio(file_storage):
    db = current_app.extensions.get("mongo_db")
    if db is None:
        raise RuntimeError("MongoDB is unavailable for upload storage")

    original_name = secure_filename(file_storage.filename or "")
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError("Only audio files are allowed (.mp3, .wav, .m4a, .ogg, .aac, .flac, .webm)")

    filename = original_name or f"{uuid4().hex}{suffix or '.bin'}"
    file_storage.stream.seek(0)
    content = file_storage.stream.read()
    if len(content) > MAX_AUDIO_UPLOAD_SIZE:
        raise ValueError("Audio file is too large (max 20MB)")

    result = db.notes_audio_blobs.insert_one(
        {
            "filename": filename,
            "content_type": file_storage.mimetype or "application/octet-stream",
            "data": Binary(content),
        }
    )
    file_id = result.inserted_id

    return {
        "audio_url": url_for("main.notes_audio_media", media_id=str(file_id), filename=filename),
        "public_id": f"mongo:{file_id}",
        "filename": filename,
    }


def delete_note_audio(public_id: str):
    if not public_id or not public_id.startswith("mongo:"):
        return

    object_id_raw = public_id.removeprefix("mongo:").strip()
    if not ObjectId.is_valid(object_id_raw):
        return

    db = current_app.extensions.get("mongo_db")
    if db is None:
        return

    db.notes_audio_blobs.delete_one({"_id": ObjectId(object_id_raw)})


def upload_research_pdf(file_storage):
    db = current_app.extensions.get("mongo_db")
    if db is None:
        raise RuntimeError("MongoDB is unavailable for upload storage")

    original_name = secure_filename(file_storage.filename or "")
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_PDF_EXTENSIONS:
        raise ValueError("Only PDF files are allowed (.pdf)")

    filename = original_name or f"{uuid4().hex}.pdf"
    file_storage.stream.seek(0)
    content = file_storage.stream.read()
    if len(content) > MAX_PDF_UPLOAD_SIZE:
        raise ValueError("PDF file is too large (max 25MB)")

    result = db.research_pdf_blobs.insert_one(
        {
            "filename": filename,
            "content_type": "application/pdf",
            "data": Binary(content),
        }
    )
    file_id = result.inserted_id

    return {
        "pdf_url": url_for("main.research_pdf_media", media_id=str(file_id), filename=filename),
        "public_id": f"mongo:{file_id}",
        "filename": filename,
    }


def delete_research_pdf(public_id: str):
    if not public_id or not public_id.startswith("mongo:"):
        return

    object_id_raw = public_id.removeprefix("mongo:").strip()
    if not ObjectId.is_valid(object_id_raw):
        return

    db = current_app.extensions.get("mongo_db")
    if db is None:
        return

    db.research_pdf_blobs.delete_one({"_id": ObjectId(object_id_raw)})
