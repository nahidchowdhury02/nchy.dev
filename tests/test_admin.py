import io
from datetime import datetime, timezone

from app.services.books_service import BooksService


def login(client):
    username = client.application.config["ADMIN_USERNAME"]
    password = client.application.config["ADMIN_PASSWORD"]
    return client.post(
        "/admin/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_admin_login_success(client):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/manage")


def test_admin_login_invalid_password(client):
    username = client.application.config["ADMIN_USERNAME"]
    response = client.post(
        "/admin/login",
        data={"username": username, "password": "wrong-password"},
        follow_redirects=False,
    )
    assert response.status_code == 401

    db = client.application.extensions["mongo_db"]
    attempt = db.audit_logs.find_one({"action": "auth.login_failed"})
    assert attempt is not None
    assert attempt["metadata"]["attempted_username"] == username
    assert attempt["metadata"]["attempted_password"] == "wrong-password"


def test_admin_login_falls_back_to_env_when_db_unavailable(client):
    client.application.extensions["mongo_db"] = None
    client.application.extensions["mongo_client"] = None

    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/manage")


def test_admin_book_edit_updates_record(app, client):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    inserted = db.books.insert_one(
        {
            "slug": "sample-book",
            "original_title": "Sample Book",
            "title": "Sample Book",
            "subtitle": "",
            "authors": ["Old Author"],
            "first_publish_year": 2001,
            "cover_url": "https://example.com/old.jpg",
            "description": "old",
            "google_info": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    login(client)
    response = client.post(
        f"/admin/books/{inserted.inserted_id}/edit",
        data={
            "title": "Sample Book Updated",
            "slug": "sample-book-updated",
            "author": "New Author",
            "subtitle": "Updated subtitle",
            "first_publish_year": "2010",
            "cover_url": "https://example.com/new.jpg",
            "description": "new",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = db.books.find_one({"_id": inserted.inserted_id})
    assert updated["title"] == "Sample Book Updated"
    assert updated["authors"] == ["New Author"]


def test_admin_book_create_and_delete(app, client):
    db = app.extensions["mongo_db"]

    login(client)
    create_response = client.post(
        "/admin/books",
        data={
            "title": "Created Book",
            "slug": "created-book",
            "author": "Author One, Author Two",
            "subtitle": "A subtitle",
            "first_publish_year": "2022",
            "cover_url": "https://example.com/created.jpg",
            "description": "a created book",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    created = db.books.find_one({"slug": "created-book"})
    assert created is not None
    assert created["authors"] == ["Author One", "Author Two"]

    delete_response = client.post(f"/admin/books/{created['_id']}/delete", follow_redirects=False)
    assert delete_response.status_code == 302
    assert db.books.find_one({"_id": created["_id"]}) is None


def test_admin_books_external_search_and_import(app, client, monkeypatch):
    db = app.extensions["mongo_db"]

    def fake_search(self, query, limit_raw=None):
        assert query == "9780140328721"
        return [
            {
                "title": "Matilda",
                "subtitle": "",
                "author": "Roald Dahl",
                "authors": ["Roald Dahl"],
                "first_publish_year": 1988,
                "cover_url": "https://covers.openlibrary.org/b/id/123-L.jpg",
                "description": "",
                "source_open_key": "/works/OL45804W",
                "source_isbn": "9780140328721",
            }
        ]

    monkeypatch.setattr(BooksService, "search_open_books", fake_search)

    login(client)

    search_response = client.get("/admin/books?external_q=9780140328721")
    assert search_response.status_code == 200
    assert "Matilda" in search_response.get_data(as_text=True)

    import_response = client.post(
        "/admin/books/import",
        data={
            "external_q": "9780140328721",
            "title": "Matilda",
            "subtitle": "",
            "author": "Roald Dahl",
            "first_publish_year": "1988",
            "cover_url": "https://covers.openlibrary.org/b/id/123-L.jpg",
            "description": "",
            "source_open_key": "/works/OL45804W",
            "source_isbn": "9780140328721",
        },
        follow_redirects=False,
    )
    assert import_response.status_code == 302
    assert import_response.headers["Location"].endswith("?external_q=9780140328721")

    imported = db.books.find_one({"slug": "matilda"})
    assert imported is not None
    assert imported["title"] == "Matilda"
    assert imported["authors"] == ["Roald Dahl"]
    assert imported["open_book_key"] == "/works/OL45804W"
    assert imported["isbn"] == "9780140328721"

    audit = db.audit_logs.find_one({"action": "books.import", "entity_id": str(imported["_id"])})
    assert audit is not None


def test_admin_book_delete_requires_reading_removal(app, client):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    inserted = db.books.insert_one(
        {
            "slug": "reading-protected-book",
            "original_title": "Reading Protected Book",
            "title": "Reading Protected Book",
            "subtitle": "",
            "authors": ["Reader Author"],
            "first_publish_year": 2024,
            "cover_url": "https://example.com/protected.jpg",
            "description": "protected",
            "google_info": None,
            "created_at": now,
            "updated_at": now,
        }
    )
    db.reading_list.insert_one(
        {
            "book_id": inserted.inserted_id,
            "created_at": now,
            "updated_at": now,
        }
    )

    login(client)
    response = client.post(f"/admin/books/{inserted.inserted_id}/delete", follow_redirects=False)

    assert response.status_code == 302
    assert db.books.find_one({"_id": inserted.inserted_id}) is not None


def test_admin_reading_add_and_remove(app, client):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    inserted = db.books.insert_one(
        {
            "slug": "reading-sample-book",
            "original_title": "Reading Sample Book",
            "title": "Reading Sample Book",
            "subtitle": "",
            "authors": ["Reader Author"],
            "first_publish_year": 2024,
            "cover_url": "https://example.com/reading.jpg",
            "description": "reading",
            "google_info": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    login(client)
    add_response = client.post(
        "/admin/reading",
        data={"book_id": str(inserted.inserted_id)},
        follow_redirects=False,
    )
    assert add_response.status_code == 302

    entry = db.reading_list.find_one({"book_id": inserted.inserted_id})
    assert entry is not None

    remove_response = client.post(f"/admin/reading/{entry['_id']}/delete", follow_redirects=False)
    assert remove_response.status_code == 302
    assert db.reading_list.find_one({"_id": entry["_id"]}) is None


def test_admin_gallery_create_and_delete(app, client):
    db = app.extensions["mongo_db"]

    login(client)
    create_response = client.post(
        "/admin/gallery",
        data={
            "category": "sketches",
            "title": "A sketch",
            "caption": "caption",
            "image_url": "https://example.com/a.jpg",
            "storage_public_id": "img/a",
            "sort_order": "3",
            "is_published": "1",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    item = db.gallery_items.find_one({"title": "A sketch"})
    assert item is not None

    delete_response = client.post(f"/admin/gallery/{item['_id']}/delete", follow_redirects=False)
    assert delete_response.status_code == 302
    assert db.gallery_items.find_one({"_id": item["_id"]}) is None


def test_admin_gallery_archive_and_unarchive(app, client):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    inserted = db.gallery_items.insert_one(
        {
            "category": "sketches",
            "title": "Archive me",
            "caption": "caption",
            "image_url": "https://example.com/archive-me.jpg",
            "storage_public_id": "img/archive-me",
            "sort_order": 0,
            "is_published": True,
            "created_at": now,
            "updated_at": now,
        }
    )

    login(client)
    archive_response = client.post(
        f"/admin/gallery/{inserted.inserted_id}/archive",
        data={"category": "sketches"},
        follow_redirects=False,
    )
    assert archive_response.status_code == 302

    archived = db.gallery_items.find_one({"_id": inserted.inserted_id})
    assert archived is not None
    assert archived["is_published"] is False
    assert db.audit_logs.find_one({"action": "gallery.archive", "entity_id": str(inserted.inserted_id)}) is not None

    unarchive_response = client.post(
        f"/admin/gallery/{inserted.inserted_id}/unarchive",
        data={"category": "sketches"},
        follow_redirects=False,
    )
    assert unarchive_response.status_code == 302

    unarchived = db.gallery_items.find_one({"_id": inserted.inserted_id})
    assert unarchived is not None
    assert unarchived["is_published"] is True
    assert db.audit_logs.find_one({"action": "gallery.unarchive", "entity_id": str(inserted.inserted_id)}) is not None


def test_admin_gallery_upload_uses_mongo_storage(app, client):
    login(client)

    response = client.post(
        "/admin/gallery/upload",
        data={"image": (io.BytesIO(b"fake image bytes"), "sample.png", "image/png")},
        follow_redirects=False,
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["image_url"].startswith("/media/gallery/")
    assert payload["storage_public_id"].startswith("mongo:")


def test_admin_gallery_create_with_file_sets_image_url(app, client):
    db = app.extensions["mongo_db"]
    login(client)

    create_response = client.post(
        "/admin/gallery",
        data={
            "category": "sketches",
            "title": "file sketch",
            "caption": "with file",
            "sort_order": "1",
            "is_published": "1",
            "image": (io.BytesIO(b"fake image bytes"), "file-sketch.png", "image/png"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    item = db.gallery_items.find_one({"title": "file sketch"})
    assert item is not None
    assert item["image_url"].startswith("/media/gallery/")
    assert item["storage_public_id"].startswith("mongo:")


def test_admin_notes_update_existing_entry(app, client):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    inserted = db.notes_logs.insert_one(
        {
            "kind": "note",
            "title": "Original",
            "body": "Original body",
            "is_published": True,
            "source_filename": "seed.md",
            "created_at": now,
        }
    )

    login(client)
    response = client.post(
        f"/admin/notes/{inserted.inserted_id}",
        data={
            "kind": "log",
            "title": "Updated",
            "body": "Updated body",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    updated = db.notes_logs.find_one({"_id": inserted.inserted_id})
    assert updated is not None
    assert updated["kind"] == "log"
    assert updated["title"] == "Updated"
    assert updated["body"] == "Updated body"
    assert updated["is_published"] is False
    assert updated["source_filename"] == "seed.md"


def test_admin_notes_create_with_audio_upload(app, client):
    db = app.extensions["mongo_db"]
    login(client)

    response = client.post(
        "/admin/notes",
        data={
            "kind": "note",
            "title": "Audio note",
            "is_published": "1",
            "audio_file": (io.BytesIO(b"RIFFabcdWAVEfmt "), "sample.wav", "audio/wav"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert response.status_code == 302
    note = db.notes_logs.find_one({"title": "Audio note"})
    assert note is not None
    assert note.get("body", "") == ""
    assert note["audio_url"].startswith("/media/notes-audio/")
    assert note["audio_storage_public_id"].startswith("mongo:")
    assert note["audio_source_filename"] == "sample.wav"


def test_admin_notes_delete_removes_note_and_audio_blob(app, client):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    blob = db.notes_audio_blobs.insert_one(
        {
            "filename": "to-delete.wav",
            "content_type": "audio/wav",
            "data": b"RIFF",
        }
    )
    note = db.notes_logs.insert_one(
        {
            "kind": "note",
            "title": "Delete me",
            "body": "",
            "is_published": True,
            "source_filename": "",
            "audio_url": f"/media/notes-audio/{blob.inserted_id}/to-delete.wav",
            "audio_storage_public_id": f"mongo:{blob.inserted_id}",
            "audio_source_filename": "to-delete.wav",
            "created_at": now,
        }
    )

    login(client)
    response = client.post(f"/admin/notes/{note.inserted_id}/delete", follow_redirects=False)

    assert response.status_code == 302
    assert db.notes_logs.find_one({"_id": note.inserted_id}) is None
    assert db.notes_audio_blobs.find_one({"_id": blob.inserted_id}) is None


def test_admin_manage_updates_home_notice_banner(app, client):
    db = app.extensions["mongo_db"]

    login(client)
    response = client.post(
        "/admin/manage",
        data={"home_notice_banner_text": "a changed notice from admin"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/manage")

    setting = db.site_settings.find_one({"key": "home_notice_banner_text"})
    assert setting is not None
    assert setting["value"] == "a changed notice from admin"

    audit_entry = db.audit_logs.find_one({"action": "settings.update", "entity_id": "home_notice_banner_text"})
    assert audit_entry is not None


def test_home_page_uses_managed_notice_banner(app, client):
    db = app.extensions["mongo_db"]
    db.site_settings.insert_one({"key": "home_notice_banner_text", "value": "managed banner text"})

    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "managed banner text" in html


def test_admin_login_attempts_page_shows_failed_attempts(app, client):
    username = app.config["ADMIN_USERNAME"]
    client.post(
        "/admin/login",
        data={"username": username, "password": "wrong-password"},
        follow_redirects=False,
    )

    login(client)
    response = client.get("/admin/login-attempts")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Failed Login Attempts" in html
    assert username in html
    assert "wrong-password" in html
