from __future__ import annotations

import cloudinary
import cloudinary.uploader
from flask import current_app


def configure_cloudinary(app):
    cloud_name = app.config.get("CLOUDINARY_CLOUD_NAME", "")
    api_key = app.config.get("CLOUDINARY_API_KEY", "")
    api_secret = app.config.get("CLOUDINARY_API_SECRET", "")

    if not (cloud_name and api_key and api_secret):
        app.logger.warning("Cloudinary credentials are missing. Upload endpoint will be unavailable.")
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
        raise RuntimeError("Cloudinary credentials are not configured")

    result = cloudinary.uploader.upload(file_storage, folder=folder, resource_type="image")
    return {
        "image_url": result.get("secure_url"),
        "public_id": result.get("public_id"),
    }


def delete_image(public_id: str):
    if not public_id or not cloudinary_enabled():
        return
    cloudinary.uploader.destroy(public_id, resource_type="image")
