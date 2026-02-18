from datetime import datetime, timezone


def seed_many_books(app, total=30):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    docs = []
    for i in range(total):
        docs.append(
            {
                "slug": f"book-{i}",
                "original_title": f"Book {i}",
                "title": f"Book {i}",
                "subtitle": "",
                "authors": [f"Author {i}"],
                "first_publish_year": 2000 + (i % 20),
                "cover_url": f"https://example.com/{i}.jpg",
                "description": f"Desc {i}",
                "google_info": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    result = db.books.insert_many(docs)
    return result.inserted_ids


def seed_reading_entries(app, book_ids):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    docs = [{"book_id": book_id, "created_at": now, "updated_at": now} for book_id in book_ids]
    db.reading_list.insert_many(docs)


def test_reading_page_shows_only_books_in_reading_list(app, client):
    book_ids = seed_many_books(app, total=2)
    seed_reading_entries(app, [book_ids[0]])

    response = client.get("/reading")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "Book 0" in html
    assert "Book 1" not in html


def test_reading_page_shows_pagination_controls(app, client):
    book_ids = seed_many_books(app, total=30)
    seed_reading_entries(app, book_ids)

    response = client.get("/reading")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "Page 1 of 2" in html
    assert 'href="/reading?page=2"' in html


def test_reading_page_two_renders_and_has_previous(app, client):
    book_ids = seed_many_books(app, total=30)
    seed_reading_entries(app, book_ids)

    response = client.get("/reading?page=2")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "Page 2 of 2" in html
    assert 'href="/reading?page=1"' in html
