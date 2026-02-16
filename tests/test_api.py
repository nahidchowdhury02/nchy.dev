from datetime import datetime, timezone


def seed_books(app):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    db.books.insert_many(
        [
            {
                "slug": "book-one",
                "original_title": "Book One",
                "title": "Book One",
                "subtitle": "",
                "authors": ["Author One"],
                "first_publish_year": 2001,
                "cover_url": "https://example.com/one.jpg",
                "description": "One",
                "google_info": None,
                "created_at": now,
                "updated_at": now,
            },
            {
                "slug": "book-two",
                "original_title": "Book Two",
                "title": "Book Two",
                "subtitle": "",
                "authors": ["Author Two"],
                "first_publish_year": 2002,
                "cover_url": "https://example.com/two.jpg",
                "description": "Two",
                "google_info": None,
                "created_at": now,
                "updated_at": now,
            },
        ]
    )


def seed_gallery(app):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    db.gallery_items.insert_many(
        [
            {
                "category": "sketches",
                "title": "Sketch A",
                "caption": "",
                "image_url": "https://example.com/sketch-a.jpg",
                "storage_public_id": "x/sketch-a",
                "sort_order": 1,
                "is_published": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "category": "moments",
                "title": "Moment A",
                "caption": "",
                "image_url": "https://example.com/moment-a.jpg",
                "storage_public_id": "x/moment-a",
                "sort_order": 1,
                "is_published": False,
                "created_at": now,
                "updated_at": now,
            },
        ]
    )


def test_books_api_supports_pagination(app, client):
    seed_books(app)

    response = client.get("/api/books?limit=1")
    assert response.status_code == 200

    payload = response.get_json()
    assert len(payload["items"]) == 1
    assert payload["next_cursor"] is not None


def test_book_detail_by_slug(app, client):
    seed_books(app)

    response = client.get("/api/books/book-one")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["slug"] == "book-one"


def test_gallery_api_returns_only_published(app, client):
    seed_gallery(app)

    response = client.get("/api/gallery?category=sketches")
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["title"] == "Sketch A"


def test_healthz_reports_ok_with_db(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
