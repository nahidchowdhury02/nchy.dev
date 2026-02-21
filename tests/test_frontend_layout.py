from datetime import datetime, timezone

import pytest


PUBLIC_ROUTES = [
    "/",
    "/books",
    "/github-research",
    "/gallery",
    "/gallery/sketches",
    "/gallery/moments",
    "/gallery/all",
    "/music",
    "/reading",
    "/notes",
    "/contact",
]

ADMIN_ROUTES = [
    "/admin/login",
    "/admin/manage",
    "/admin/books",
    "/admin/reading",
    "/admin/gallery",
    "/admin/github-research",
    "/admin/music",
    "/admin/manage/notes",
]


def login(client):
    username = client.application.config["ADMIN_USERNAME"]
    password = client.application.config["ADMIN_PASSWORD"]
    return client.post(
        "/admin/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_public_routes_include_viewport_and_layout(client, path):
    response = client.get(path)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="viewport"' in html
    assert 'class="app-shell"' in html


@pytest.mark.parametrize("path", ADMIN_ROUTES)
def test_admin_routes_include_viewport_and_layout(app, client, path):
    if path != "/admin/login":
        login_response = login(client)
        assert login_response.status_code == 302

    response = client.get(path)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="viewport"' in html
    assert 'class="app-shell"' in html


def test_admin_books_contains_table_and_cards(client):
    login_response = login(client)
    assert login_response.status_code == 302

    response = client.get("/admin/books")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    assert "books-table" in html
    assert "books-cards" in html


def test_admin_book_edit_page_uses_shared_layout(app, client):
    db = app.extensions["mongo_db"]
    now = datetime.now(timezone.utc)
    inserted = db.books.insert_one(
        {
            "slug": "layout-book",
            "original_title": "Layout Book",
            "title": "Layout Book",
            "subtitle": "",
            "authors": ["Layout Author"],
            "first_publish_year": 2020,
            "cover_url": "https://example.com/layout.jpg",
            "description": "Layout",
            "google_info": None,
            "created_at": now,
            "updated_at": now,
        }
    )

    login_response = login(client)
    assert login_response.status_code == 302

    response = client.get(f"/admin/books/{inserted.inserted_id}/edit")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'name="viewport"' in html
    assert 'class="app-shell"' in html
