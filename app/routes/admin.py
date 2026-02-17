from __future__ import annotations

import time

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from ..auth import login_admin, logout_admin, require_admin
from ..db import get_db
from ..extensions import limiter
from ..repositories.audit_repo import AuditRepository
from ..services.auth_service import AuthService
from ..services.books_service import BooksService
from ..services.gallery_service import GalleryService
from ..services.music_service import MusicService
from ..services.notes_service import NotesService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _auth_service() -> AuthService:
    return AuthService(get_db())


def _books_service() -> BooksService:
    return BooksService(get_db())


def _gallery_service() -> GalleryService:
    return GalleryService(get_db())


def _notes_service() -> NotesService:
    return NotesService(get_db())


def _music_service() -> MusicService:
    return MusicService(get_db())


def _audit_repo() -> AuditRepository:
    return AuditRepository(get_db())


def _safe_next(next_path: str | None):
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return url_for("admin.manage")


def _admin_actor() -> str:
    return session.get("admin_username", "system")


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("LOGIN_RATE_LIMIT", "5 per minute"), methods=["POST"])
def login():
    next_path = request.args.get("next") or request.form.get("next")

    if request.method == "GET":
        return render_template("admin/login.html", next_path=next_path or "")

    auth_service = _auth_service()

    now = time.time()
    locked_until = session.get("admin_locked_until", 0)
    if locked_until and now < locked_until:
        wait_seconds = int(locked_until - now)
        flash(f"Too many attempts. Try again in {wait_seconds}s.", "error")
        return render_template("admin/login.html", next_path=next_path or ""), 429

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    user = None
    if auth_service.available():
        user = auth_service.authenticate_admin(username=username, password=password)
    else:
        fallback_username = (current_app.config.get("ADMIN_USERNAME") or "").strip()
        fallback_password = current_app.config.get("ADMIN_PASSWORD") or ""
        if (
            fallback_username
            and fallback_password
            and username == fallback_username
            and password == fallback_password
        ):
            user = {
                "id": f"env:{fallback_username}",
                "username": fallback_username,
            }
            flash("Database unavailable. Signed in using environment credentials.", "warning")

    if not user:
        failed = int(session.get("admin_failed_attempts", 0)) + 1
        session["admin_failed_attempts"] = failed

        if failed >= 3:
            backoff_seconds = min(300, 2 ** (failed - 2))
            session["admin_locked_until"] = now + backoff_seconds

        flash("Invalid username or password", "error")
        return render_template("admin/login.html", next_path=next_path or ""), 401

    login_admin(user)
    flash("Signed in successfully", "success")
    return redirect(_safe_next(next_path))


@admin_bp.route("/logout", methods=["POST"])
@require_admin
def logout():
    logout_admin()
    flash("Signed out", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@require_admin
def index():
    return redirect(url_for("admin.manage"))


@admin_bp.route("/content")
@require_admin
def content():
    return redirect(url_for("admin.manage"))


@admin_bp.route("/manage")
@require_admin
def manage():
    books_service = _books_service()
    gallery_service = _gallery_service()
    return render_template(
        "admin/manage/content.html",
        books_count=books_service.count_books(),
        gallery_count=gallery_service.count_items(),
        music_count=_music_service().count_links(),
        notes_count=_notes_service().count_entries(),
    )


@admin_bp.route("/books")
@admin_bp.route("/manage/books")
@require_admin
def books():
    query = request.args.get("q", "").strip()
    books_service = _books_service()
    books = books_service.list_admin_books(query=query)
    return render_template("admin/books.html", books=books, query=query)


@admin_bp.route("/notes", methods=["GET", "POST"])
@admin_bp.route("/manage/notes", methods=["GET", "POST"])
@require_admin
def notes():
    notes_service = _notes_service()

    if request.method == "POST":
        try:
            notes_service.create_entry(request.form, request.files.get("upload_file"))
            _audit_repo().log(
                actor=_admin_actor(),
                action="notes.create",
                entity="notes_log",
            )
            flash("Notes/log entry saved to MongoDB", "success")
            return redirect(url_for("admin.notes"))
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")

    entries = notes_service.list_admin_entries(limit_raw="200")
    return render_template("admin/manage/notes.html", entries=entries)


@admin_bp.route("/books/<book_id>/edit", methods=["GET", "POST"])
@require_admin
def book_edit(book_id):
    books_service = _books_service()

    if request.method == "POST":
        try:
            updated = books_service.update_admin_book(book_id=book_id, form_data=request.form)
            if not updated:
                flash("Book not found", "error")
                return redirect(url_for("admin.books"))

            _audit_repo().log(
                actor=_admin_actor(),
                action="books.update",
                entity="book",
                entity_id=book_id,
            )
            flash("Book updated", "success")
            return redirect(url_for("admin.book_edit", book_id=book_id))
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")

    book = books_service.get_admin_book(book_id)
    if not book:
        flash("Book not found", "error")
        return redirect(url_for("admin.books"))

    return render_template("admin/book_edit.html", book=book)


@admin_bp.route("/gallery", methods=["GET", "POST"])
@admin_bp.route("/manage/gallery", methods=["GET", "POST"])
@require_admin
def gallery():
    gallery_service = _gallery_service()

    if request.method == "POST":
        try:
            gallery_service.create_item(request.form, request.files.get("image"))
            _audit_repo().log(
                actor=_admin_actor(),
                action="gallery.create",
                entity="gallery_item",
            )
            flash("Gallery item created", "success")
            return redirect(url_for("admin.gallery"))
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")

    category = request.args.get("category", "all")
    items = gallery_service.list_admin_items(category=category)
    return render_template("admin/gallery.html", items=items, selected_category=category)


@admin_bp.route("/gallery/<item_id>", methods=["POST"])
@require_admin
def gallery_update(item_id):
    gallery_service = _gallery_service()
    try:
        updated = gallery_service.update_item(
            item_id=item_id,
            payload=request.form,
            file_storage=request.files.get("image"),
        )
        if not updated:
            flash("Gallery item not found", "error")
        else:
            _audit_repo().log(
                actor=_admin_actor(),
                action="gallery.update",
                entity="gallery_item",
                entity_id=item_id,
            )
            flash("Gallery item updated", "success")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin.gallery"))


@admin_bp.route("/gallery/<item_id>/delete", methods=["POST"])
@require_admin
def gallery_delete(item_id):
    gallery_service = _gallery_service()

    try:
        deleted = gallery_service.delete_item(item_id=item_id)
        if deleted:
            _audit_repo().log(
                actor=_admin_actor(),
                action="gallery.delete",
                entity="gallery_item",
                entity_id=item_id,
            )
            flash("Gallery item deleted", "success")
        else:
            flash("Gallery item not found", "error")
    except RuntimeError as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin.gallery"))


@admin_bp.route("/gallery/upload", methods=["POST"])
@require_admin
def gallery_upload():
    gallery_service = _gallery_service()
    file_obj = request.files.get("image")

    try:
        payload = gallery_service.upload_item_image(file_obj)
        return jsonify(payload)
    except (ValueError, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/music", methods=["GET", "POST"])
@admin_bp.route("/manage/music", methods=["GET", "POST"])
@require_admin
def music():
    music_service = _music_service()

    if request.method == "POST":
        try:
            music_service.create_link(request.form)
            _audit_repo().log(
                actor=_admin_actor(),
                action="music.create",
                entity="music_link",
            )
            flash("Music link created", "success")
            return redirect(url_for("admin.music"))
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")

    links = music_service.list_admin_links()
    return render_template("admin/music.html", links=links)


@admin_bp.route("/music/<link_id>", methods=["POST"])
@require_admin
def music_update(link_id):
    music_service = _music_service()
    try:
        updated = music_service.update_link(link_id, request.form)
        if not updated:
            flash("Music link not found", "error")
        else:
            _audit_repo().log(
                actor=_admin_actor(),
                action="music.update",
                entity="music_link",
                entity_id=link_id,
            )
            flash("Music link updated", "success")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.music"))


@admin_bp.route("/music/<link_id>/delete", methods=["POST"])
@require_admin
def music_delete(link_id):
    music_service = _music_service()
    try:
        deleted = music_service.delete_link(link_id)
        if deleted:
            _audit_repo().log(
                actor=_admin_actor(),
                action="music.delete",
                entity="music_link",
                entity_id=link_id,
            )
            flash("Music link deleted", "success")
        else:
            flash("Music link not found", "error")
    except RuntimeError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.music"))
