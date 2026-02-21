from __future__ import annotations

import time

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from ..auth import login_admin, logout_admin, require_admin
from ..db import get_db
from ..extensions import limiter
from ..repositories.audit_repo import AuditRepository
from ..services.auth_service import AuthService
from ..services.books_service import BooksService
from ..services.certification_service import CertificationService
from ..services.gallery_service import GalleryService
from ..services.github_research_service import GithubResearchService
from ..services.music_service import MusicService
from ..services.notes_service import NotesService
from ..services.reading_service import ReadingService
from ..services.site_settings_service import SiteSettingsService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _auth_service() -> AuthService:
    return AuthService(get_db())


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


def _audit_repo() -> AuditRepository:
    return AuditRepository(get_db())


def _safe_next(next_path: str | None):
    if next_path and next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return url_for("admin.manage")


def _admin_actor() -> str:
    return session.get("admin_username", "system")


def _gallery_redirect():
    category = (request.form.get("category") or request.args.get("category") or "").strip().lower()
    if category in {"all", "sketches", "moments"}:
        return redirect(url_for("admin.gallery", category=category))
    return redirect(url_for("admin.gallery"))


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config.get("LOGIN_RATE_LIMIT", "5 per minute"), methods=["POST"])
def login():
    next_path = request.args.get("next") or request.form.get("next")

    if request.method == "GET":
        return render_template("admin/login.html", next_path=next_path or "")

    auth_service = _auth_service()
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    remote_addr = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
    user_agent = request.user_agent.string or ""

    now = time.time()
    locked_until = session.get("admin_locked_until", 0)
    if locked_until and now < locked_until:
        wait_seconds = int(locked_until - now)
        auth_service.log_failed_admin_login(
            username=username,
            password=password,
            reason="locked_out",
            remote_addr=remote_addr,
            user_agent=user_agent,
        )
        flash(f"Too many attempts. Try again in {wait_seconds}s.", "error")
        return render_template("admin/login.html", next_path=next_path or ""), 429

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

        auth_service.log_failed_admin_login(
            username=username,
            password=password,
            reason="invalid_credentials",
            remote_addr=remote_addr,
            user_agent=user_agent,
        )
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


@admin_bp.route("/manage", methods=["GET", "POST"])
@require_admin
def manage():
    site_settings_service = _site_settings_service()

    if request.method == "POST":
        try:
            site_settings_service.update_home_notice_banner_text(request.form.get("home_notice_banner_text"))
            _audit_repo().log(
                actor=_admin_actor(),
                action="settings.update",
                entity="site_setting",
                entity_id="home_notice_banner_text",
            )
            flash("Homepage notice banner updated", "success")
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("admin.manage"))

    books_service = _books_service()
    gallery_service = _gallery_service()
    return render_template(
        "admin/manage/content.html",
        books_count=books_service.count_books(),
        reading_count=_reading_service().count_entries(),
        certification_count=_certification_service().count_badges(),
        gallery_count=gallery_service.count_items(),
        github_research_count=_github_research_service().count_items(),
        music_count=_music_service().count_links(),
        notes_count=_notes_service().count_entries(),
        failed_logins_count=_auth_service().count_failed_admin_logins(),
        home_notice_banner_text=site_settings_service.get_home_notice_banner_text(),
    )


@admin_bp.route("/certifications", methods=["GET", "POST"])
@admin_bp.route("/manage/certifications", methods=["GET", "POST"])
@require_admin
def certifications():
    certification_service = _certification_service()

    if request.method == "POST":
        try:
            created = certification_service.create_badge(request.form)
            _audit_repo().log(
                actor=_admin_actor(),
                action="certifications.create",
                entity="certification",
                entity_id=created.get("id", ""),
                metadata={"badge_uuid": created.get("badge_uuid", "")},
            )
            flash("Certification badge created", "success")
            return redirect(url_for("admin.certifications"))
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")

    badges = certification_service.list_admin_badges()
    return render_template("admin/certifications.html", badges=badges)


@admin_bp.route("/certifications/<badge_id>", methods=["POST"])
@require_admin
def certifications_update(badge_id):
    certification_service = _certification_service()
    try:
        updated = certification_service.update_badge(badge_id, request.form)
        if not updated:
            flash("Certification badge not found", "error")
        else:
            _audit_repo().log(
                actor=_admin_actor(),
                action="certifications.update",
                entity="certification",
                entity_id=badge_id,
                metadata={"badge_uuid": updated.get("badge_uuid", "")},
            )
            flash("Certification badge updated", "success")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.certifications"))


@admin_bp.route("/certifications/<badge_id>/delete", methods=["POST"])
@require_admin
def certifications_delete(badge_id):
    certification_service = _certification_service()
    try:
        deleted = certification_service.delete_badge(badge_id)
        if deleted:
            _audit_repo().log(
                actor=_admin_actor(),
                action="certifications.delete",
                entity="certification",
                entity_id=badge_id,
            )
            flash("Certification badge deleted", "success")
        else:
            flash("Certification badge not found", "error")
    except RuntimeError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.certifications"))


@admin_bp.route("/books", methods=["GET", "POST"])
@admin_bp.route("/manage/books", methods=["GET", "POST"])
@require_admin
def books():
    books_service = _books_service()

    if request.method == "POST":
        try:
            created = books_service.create_admin_book(request.form)
            _audit_repo().log(
                actor=_admin_actor(),
                action="books.create",
                entity="book",
                entity_id=created.get("id", ""),
            )
            flash("Book added", "success")
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("admin.books"))

    query = request.args.get("q", "").strip()
    external_query = request.args.get("external_q", "").strip()
    books = books_service.list_admin_books(query=query)
    external_books = []
    if external_query:
        external_books = books_service.search_open_books(
            query=external_query,
            limit_raw=request.args.get("external_limit"),
        )
    return render_template(
        "admin/books.html",
        books=books,
        query=query,
        external_query=external_query,
        external_books=external_books,
    )


@admin_bp.route("/books/import", methods=["POST"])
@require_admin
def books_import():
    books_service = _books_service()
    external_query = (request.form.get("external_q") or "").strip()

    try:
        created = books_service.create_admin_book_from_open_result(request.form)
        _audit_repo().log(
            actor=_admin_actor(),
            action="books.import",
            entity="book",
            entity_id=created.get("id", ""),
            metadata={
                "source_open_key": (request.form.get("source_open_key") or "").strip(),
                "source_isbn": (request.form.get("source_isbn") or "").strip(),
            },
        )
        flash("Book imported", "success")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")

    if external_query:
        return redirect(url_for("admin.books", external_q=external_query))
    return redirect(url_for("admin.books"))


@admin_bp.route("/reading", methods=["GET", "POST"])
@admin_bp.route("/manage/reading", methods=["GET", "POST"])
@require_admin
def reading():
    books_service = _books_service()
    reading_service = _reading_service()

    query = (request.form.get("q") or request.args.get("q") or "").strip()

    if request.method == "POST":
        try:
            created = reading_service.add_book(
                request.form.get("book_id", ""),
                reading_note=request.form.get("reading_note", ""),
            )
            _audit_repo().log(
                actor=_admin_actor(),
                action="reading.create",
                entity="reading_item",
                entity_id=created.get("id", ""),
                metadata={"book_id": created.get("book_id", "")},
            )
            flash("Book added to reading list", "success")
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")

        if query:
            return redirect(url_for("admin.reading", q=query))
        return redirect(url_for("admin.reading"))

    books = books_service.list_admin_books(query=query, limit_raw="200")
    entries = reading_service.list_admin_entries(limit_raw="200")
    return render_template("admin/manage/reading.html", books=books, entries=entries, query=query)


@admin_bp.route("/reading/<entry_id>", methods=["POST"])
@require_admin
def reading_update(entry_id):
    query = (request.form.get("q") or "").strip()
    reading_service = _reading_service()

    try:
        updated = reading_service.update_entry_note(entry_id, request.form.get("reading_note", ""))
        if not updated:
            flash("Reading list entry not found", "error")
        else:
            _audit_repo().log(
                actor=_admin_actor(),
                action="reading.update",
                entity="reading_item",
                entity_id=entry_id,
            )
            flash("Reading note updated", "success")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")

    if query:
        return redirect(url_for("admin.reading", q=query))
    return redirect(url_for("admin.reading"))


@admin_bp.route("/reading/<entry_id>/delete", methods=["POST"])
@require_admin
def reading_delete(entry_id):
    query = (request.form.get("q") or "").strip()
    reading_service = _reading_service()

    try:
        deleted = reading_service.remove_entry(entry_id)
        if deleted:
            _audit_repo().log(
                actor=_admin_actor(),
                action="reading.delete",
                entity="reading_item",
                entity_id=entry_id,
            )
            flash("Book removed from reading list", "success")
        else:
            flash("Reading list entry not found", "error")
    except RuntimeError as exc:
        flash(str(exc), "error")

    if query:
        return redirect(url_for("admin.reading", q=query))
    return redirect(url_for("admin.reading"))


@admin_bp.route("/notes", methods=["GET", "POST"])
@admin_bp.route("/manage/notes", methods=["GET", "POST"])
@require_admin
def notes():
    notes_service = _notes_service()

    if request.method == "POST":
        try:
            notes_service.create_entry(
                request.form,
                request.files.get("upload_file"),
                request.files.get("audio_file"),
            )
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


@admin_bp.route("/notes/<entry_id>", methods=["POST"])
@require_admin
def notes_update(entry_id):
    notes_service = _notes_service()
    try:
        updated = notes_service.update_entry(
            entry_id,
            request.form,
            request.files.get("upload_file"),
            request.files.get("audio_file"),
        )
        if not updated:
            flash("Notes/log entry not found", "error")
        else:
            _audit_repo().log(
                actor=_admin_actor(),
                action="notes.update",
                entity="notes_log",
                entity_id=entry_id,
            )
            flash("Notes/log entry updated", "success")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin.notes"))


@admin_bp.route("/notes/<entry_id>/delete", methods=["POST"])
@require_admin
def notes_delete(entry_id):
    notes_service = _notes_service()
    try:
        deleted = notes_service.remove_entry(entry_id)
        if deleted:
            _audit_repo().log(
                actor=_admin_actor(),
                action="notes.delete",
                entity="notes_log",
                entity_id=entry_id,
            )
            flash("Notes/log entry deleted", "success")
        else:
            flash("Notes/log entry not found", "error")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin.notes"))


@admin_bp.route("/login-attempts")
@admin_bp.route("/manage/login-attempts")
@require_admin
def login_attempts():
    auth_service = _auth_service()
    attempts = auth_service.list_failed_admin_logins(limit_raw=request.args.get("limit"))
    return render_template("admin/login_attempts.html", attempts=attempts)


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


@admin_bp.route("/books/<book_id>/delete", methods=["POST"])
@require_admin
def book_delete(book_id):
    query = (request.form.get("q") or "").strip()
    books_service = _books_service()

    try:
        deleted = books_service.delete_admin_book(book_id=book_id)
        if deleted:
            _audit_repo().log(
                actor=_admin_actor(),
                action="books.delete",
                entity="book",
                entity_id=book_id,
            )
            flash("Book deleted", "success")
        else:
            flash("Book not found", "error")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")

    if query:
        return redirect(url_for("admin.books", q=query))
    return redirect(url_for("admin.books"))


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
            return _gallery_redirect()
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

    return _gallery_redirect()


@admin_bp.route("/gallery/<item_id>/archive", methods=["POST"])
@require_admin
def gallery_archive(item_id):
    gallery_service = _gallery_service()

    try:
        updated = gallery_service.set_item_archived(item_id=item_id, archived=True)
        if updated:
            _audit_repo().log(
                actor=_admin_actor(),
                action="gallery.archive",
                entity="gallery_item",
                entity_id=item_id,
            )
            flash("Gallery item archived", "success")
        else:
            flash("Gallery item not found", "error")
    except RuntimeError as exc:
        flash(str(exc), "error")

    return _gallery_redirect()


@admin_bp.route("/gallery/<item_id>/unarchive", methods=["POST"])
@require_admin
def gallery_unarchive(item_id):
    gallery_service = _gallery_service()

    try:
        updated = gallery_service.set_item_archived(item_id=item_id, archived=False)
        if updated:
            _audit_repo().log(
                actor=_admin_actor(),
                action="gallery.unarchive",
                entity="gallery_item",
                entity_id=item_id,
            )
            flash("Gallery item unarchived", "success")
        else:
            flash("Gallery item not found", "error")
    except RuntimeError as exc:
        flash(str(exc), "error")

    return _gallery_redirect()


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

    return _gallery_redirect()


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


@admin_bp.route("/github-research", methods=["GET", "POST"])
@admin_bp.route("/manage/github-research", methods=["GET", "POST"])
@require_admin
def github_research():
    github_research_service = _github_research_service()

    if request.method == "POST":
        try:
            created = github_research_service.create_item(request.form, request.files.get("pdf_file"))
            _audit_repo().log(
                actor=_admin_actor(),
                action="github_research.create",
                entity="github_research_item",
                entity_id=created.get("id", ""),
                metadata={"kind": created.get("kind", "")},
            )
            flash("Item created", "success")
            return redirect(url_for("admin.github_research"))
        except (ValueError, RuntimeError) as exc:
            flash(str(exc), "error")

    items = github_research_service.list_admin_items()
    return render_template("admin/github_research.html", items=items)


@admin_bp.route("/github-research/<item_id>", methods=["POST"])
@require_admin
def github_research_update(item_id):
    github_research_service = _github_research_service()
    try:
        updated = github_research_service.update_item(item_id, request.form, request.files.get("pdf_file"))
        if not updated:
            flash("Item not found", "error")
        else:
            _audit_repo().log(
                actor=_admin_actor(),
                action="github_research.update",
                entity="github_research_item",
                entity_id=item_id,
                metadata={"kind": updated.get("kind", "")},
            )
            flash("Item updated", "success")
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.github_research"))


@admin_bp.route("/github-research/<item_id>/delete", methods=["POST"])
@require_admin
def github_research_delete(item_id):
    github_research_service = _github_research_service()
    try:
        deleted = github_research_service.delete_item(item_id)
        if deleted:
            _audit_repo().log(
                actor=_admin_actor(),
                action="github_research.delete",
                entity="github_research_item",
                entity_id=item_id,
            )
            flash("Item removed", "success")
        else:
            flash("Item not found", "error")
    except RuntimeError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin.github_research"))
