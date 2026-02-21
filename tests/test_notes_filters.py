from datetime import datetime, timezone


def seed_notes(app):
    db = app.extensions["mongo_db"]
    db.notes_logs.insert_many(
        [
            {
                "kind": "note",
                "title": "Note Older",
                "body": "old note",
                "is_published": True,
                "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
            },
            {
                "kind": "log",
                "title": "Log Newer",
                "body": "new log",
                "is_published": True,
                "created_at": datetime(2025, 2, 1, tzinfo=timezone.utc),
            },
            {
                "kind": "note",
                "title": "Note Hidden",
                "body": "hidden",
                "is_published": False,
                "created_at": datetime(2025, 3, 1, tzinfo=timezone.utc),
            },
        ]
    )


def test_notes_kind_filter_only_logs(app, client):
    seed_notes(app)

    response = client.get("/notes?kind=log")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Log Newer" in html
    assert "Note Older" not in html


def test_notes_sort_oldest_first(app, client):
    seed_notes(app)

    response = client.get("/notes?sort=oldest")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert html.index("Note Older") < html.index("Log Newer")


def test_notes_page_contains_svg_filter_icons(client):
    response = client.get("/notes")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "notes-kind-icons" in html
    assert "<svg" in html
