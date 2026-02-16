from bson import ObjectId
from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for

from ..db import get_db
from ..services.books_service import BooksService
from ..services.gallery_service import GalleryService
from ..services.music_service import MusicService
from ..services.notes_service import NotesService

main_bp = Blueprint("main", __name__)


def _books_service() -> BooksService:
    return BooksService(get_db())


def _gallery_service() -> GalleryService:
    return GalleryService(get_db())


def _notes_service() -> NotesService:
    return NotesService(get_db())


def _music_service() -> MusicService:
    return MusicService(get_db())


@main_bp.route("/")
def home():
    preview_books = _books_service().list_preview_books(limit=8)
    return render_template("pages/index.html", preview_books=preview_books)


@main_bp.route("/gallery")
def gallery():
    return render_template("pages/gallery.html")


@main_bp.route("/github-research")
def github_research():
    return render_template("pages/github_research.html")


@main_bp.route("/music")
def music():
    links = _music_service().list_public_links()
    return render_template("pages/music.html", links=links)


@main_bp.route("/reading")
def reading():
    page_data = _books_service().list_public_books_page(page_raw=request.args.get("page"), per_page_raw="24")
    return render_template(
        "pages/reading.html",
        books=page_data["items"],
        page=page_data["page"],
        total_pages=page_data["total_pages"],
        total_books=page_data["total"],
        has_prev=page_data["has_prev"],
        has_next=page_data["has_next"],
    )


@main_bp.route("/fun")
def fun():
    return render_template("pages/fun.html")


@main_bp.route("/notes")
def notes():
    entries = _notes_service().list_public_entries(limit_raw="100")
    return render_template("pages/notes.html", entries=entries)


@main_bp.route("/contact")
def contact():
    return render_template("pages/contact.html")


@main_bp.route("/gallery/sketches")
def gallery_sketches():
    items, _ = _gallery_service().list_public_items(category="sketches", limit_raw="24")
    return render_template("pages/gallery_sketches.html", items=items)


@main_bp.route("/gallery/moments")
def gallery_moments():
    items, _ = _gallery_service().list_public_items(category="moments", limit_raw="24")
    return render_template("pages/gallery_moments.html", items=items)


@main_bp.route("/gallery/all")
def gallery_all():
    items, _ = _gallery_service().list_public_items(category="all", limit_raw="24")
    return render_template("pages/gallery_all.html", items=items)


@main_bp.route("/edit", methods=["GET", "POST"])
def edit():
    return redirect(url_for("admin.books"))


@main_bp.route("/healthz")
def healthz():
    db = get_db()
    if db is None:
        return jsonify({"status": "degraded", "database": "unconfigured"}), 503

    try:
        db.command("ping")
    except Exception as exc:
        return jsonify({"status": "degraded", "database": "down", "error": str(exc)}), 503

    return jsonify({"status": "ok", "database": "up"})


@main_bp.route("/media/gallery/<media_id>/<path:filename>")
def gallery_media(media_id, filename):
    db = get_db()
    if db is None or not ObjectId.is_valid(media_id):
        abort(404)

    blob = db.gallery_upload_blobs.find_one({"_id": ObjectId(media_id)})
    if not blob:
        abort(404)

    return Response(
        blob.get("data", b""),
        mimetype=blob.get("content_type") or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
