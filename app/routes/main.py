from bson import ObjectId
from flask import Blueprint, Response, abort, current_app, jsonify, redirect, render_template, request, send_from_directory, url_for

from ..db import get_db
from ..services.books_service import BooksService
from ..services.certification_service import CertificationService
from ..services.gallery_service import GalleryService
from ..services.github_research_service import GithubResearchService
from ..services.music_service import MusicService
from ..services.notes_service import NotesService
from ..services.reading_service import ReadingService
from ..services.site_settings_service import SiteSettingsService

main_bp = Blueprint("main", __name__)


def _books_service() -> BooksService:
    return BooksService(get_db())


def _gallery_service() -> GalleryService:
    return GalleryService(get_db())


def _certification_service() -> CertificationService:
    return CertificationService(get_db())


def _notes_service() -> NotesService:
    return NotesService(get_db())


def _github_research_service() -> GithubResearchService:
    return GithubResearchService(get_db())


def _music_service() -> MusicService:
    return MusicService(get_db())


def _site_settings_service() -> SiteSettingsService:
    return SiteSettingsService(get_db())


def _reading_service() -> ReadingService:
    return ReadingService(get_db())


@main_bp.route("/")
def home():
    return render_template(
        "pages/index.html",
        notice_banner_text=_site_settings_service().get_home_notice_banner_text(),
    )


@main_bp.route("/gallery")
def gallery():
    return render_template("pages/gallery.html")


@main_bp.route("/github-research")
def github_research():
    github_research_service = _github_research_service()
    return render_template(
        "pages/github_research.html",
        repositories=github_research_service.list_public_repositories(),
        research_pdfs=github_research_service.list_public_research_pdfs(),
    )


@main_bp.route("/books")
def books():
    query = (request.args.get("q") or "").strip()
    page_data = _books_service().list_public_books_page(
        query=query,
        page_raw=request.args.get("page"),
        per_page_raw="24",
    )
    return render_template(
        "pages/books.html",
        books=page_data["items"],
        query=query,
        page=page_data["page"],
        total_pages=page_data["total_pages"],
        total_books=page_data["total"],
        has_prev=page_data["has_prev"],
        has_next=page_data["has_next"],
    )


@main_bp.route("/certification")
def certification():
    badges = _certification_service().list_public_badges()
    return render_template("pages/certification.html", badges=badges)


@main_bp.route("/music")
def music():
    sort = (request.args.get("sort") or "newest").strip().lower()
    if sort not in {"newest", "oldest"}:
        sort = "newest"
    links = _music_service().list_public_links(sort=sort)
    return render_template("pages/music.html", links=links, selected_sort=sort)


@main_bp.route("/reading")
def reading():
    page_data = _reading_service().list_public_books_page(page_raw=request.args.get("page"), per_page_raw="24")
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
    kind = (request.args.get("kind") or "").strip().lower()
    sort = (request.args.get("sort") or "newest").strip().lower()
    if kind not in {"note", "log"}:
        kind = ""
    if sort not in {"newest", "oldest"}:
        sort = "newest"

    entries = _notes_service().list_public_entries(limit_raw="100", kind=kind, sort=sort)
    return render_template("pages/notes.html", entries=entries, selected_kind=kind, selected_sort=sort)


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


@main_bp.route("/robots.txt")
def robots_txt():
    return send_from_directory(current_app.static_folder, "robots.txt", mimetype="text/plain")


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


@main_bp.route("/media/notes-audio/<media_id>/<path:filename>")
def notes_audio_media(media_id, filename):
    db = get_db()
    if db is None or not ObjectId.is_valid(media_id):
        abort(404)

    blob = db.notes_audio_blobs.find_one({"_id": ObjectId(media_id)})
    if not blob:
        abort(404)

    return Response(
        blob.get("data", b""),
        mimetype=blob.get("content_type") or "application/octet-stream",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@main_bp.route("/media/research-pdf/<media_id>/<path:filename>")
def research_pdf_media(media_id, filename):
    db = get_db()
    if db is None or not ObjectId.is_valid(media_id):
        abort(404)

    blob = db.research_pdf_blobs.find_one({"_id": ObjectId(media_id)})
    if not blob:
        abort(404)

    return Response(
        blob.get("data", b""),
        mimetype="application/pdf",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Content-Disposition": f'inline; filename="{blob.get("filename", "research.pdf")}"',
        },
    )
