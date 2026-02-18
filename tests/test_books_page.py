from datetime import datetime, timezone


def seed_many_books(app, total=30):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    docs = []
    for i in range(total):
        docs.append(
            {
                "slug": f"library-book-{i}",
                "original_title": f"Library Book {i}",
                "title": f"Library Book {i}",
                "subtitle": "",
                "authors": [f"Author {i}"],
                "first_publish_year": 2000 + (i % 20),
                "cover_url": f"https://example.com/library-{i}.jpg",
                "description": f"Description {i}",
                "google_info": None,
                "created_at": now,
                "updated_at": now,
            }
        )
    db.books.insert_many(docs)


def test_books_page_shows_library_books(app, client):
    seed_many_books(app, total=2)

    response = client.get("/books")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "Library Book 0" in html
    assert "Library Book 1" in html


def test_books_page_paginates(app, client):
    seed_many_books(app, total=30)

    response = client.get("/books")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "Page 1 of 2" in html
    assert 'href="/books?page=2"' in html
