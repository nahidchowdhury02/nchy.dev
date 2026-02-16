import io
from datetime import datetime, timezone


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
