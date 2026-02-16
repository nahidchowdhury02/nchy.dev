from __future__ import annotations

from pathlib import Path

import cloudinary
import cloudinary.uploader
from bson import ObjectId
from bson.binary import Binary
from flask import current_app, url_for
from werkzeug.utils import secure_filename


def configure_cloudinary(app):
    cloud_name = app.config.get("CLOUDINARY_CLOUD_NAME", "")
    api_key = app.config.get("CLOUDINARY_API_KEY", "")
    api_secret = app.config.get("CLOUDINARY_API_SECRET", "")

    if not (cloud_name and api_key and api_secret):
        app.logger.warning("Cloudinary credentials are missing. Falling back to MongoDB-backed uploads.")
        return

    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)


def cloudinary_enabled() -> bool:
    return all(
        [
            current_app.config.get("CLOUDINARY_CLOUD_NAME"),
            current_app.config.get("CLOUDINARY_API_KEY"),
            current_app.config.get("CLOUDINARY_API_SECRET"),
        ]
    )


def upload_image(file_storage, folder: str = "nchydev/gallery"):
    if not cloudinary_enabled():
        return _upload_image_to_mongo(file_storage)

    result = cloudinary.uploader.upload(file_storage, folder=folder, resource_type="image")
    return {
        "image_url": result.get("secure_url"),
        "public_id": result.get("public_id"),
    }


def delete_image(public_id: str):
    if public_id.startswith("mongo:"):
        _delete_mongo_image(public_id)
        return

    if not public_id or not cloudinary_enabled():
        return
    cloudinary.uploader.destroy(public_id, resource_type="image")


def _upload_image_to_mongo(file_storage):
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


def _delete_mongo_image(public_id: str):
    object_id_raw = public_id.removeprefix("mongo:").strip()
    if not object_id_raw or not ObjectId.is_valid(object_id_raw):
        return

    db = current_app.extensions.get("mongo_db")
    if db is None:
        return

    db.gallery_upload_blobs.delete_one({"_id": ObjectId(object_id_raw)})
