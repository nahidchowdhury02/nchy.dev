def login(client):
    username = client.application.config["ADMIN_USERNAME"]
    password = client.application.config["ADMIN_PASSWORD"]
    return client.post(
        "/admin/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_music_page_renders_embeds_from_db(app, client):
    db = app.extensions["mongo_db"]
    db.music_links.insert_one(
        {
            "title": "Sample Music",
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "youtube_id": "dQw4w9WgXcQ",
            "sort_order": 1,
            "is_published": True,
        }
    )

    response = client.get("/music")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "youtube.com/embed/dQw4w9WgXcQ" in html
    assert "<iframe" in html


def test_admin_music_create_and_update(client, app):
    db = app.extensions["mongo_db"]
    login_response = login(client)
    assert login_response.status_code == 302

    create_response = client.post(
        "/admin/music",
        data={
            "title": "Late Song",
            "youtube_url": "https://youtu.be/dQw4w9WgXcQ",
            "sort_order": "2",
            "is_published": "1",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    created = db.music_links.find_one({"title": "Late Song"})
    assert created is not None
    assert created["youtube_id"] == "dQw4w9WgXcQ"

    update_response = client.post(
        f"/admin/music/{created['_id']}",
        data={
            "title": "Late Song Updated",
            "youtube_url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
            "sort_order": "3",
            "is_published": "1",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 302

    updated = db.music_links.find_one({"_id": created["_id"]})
    assert updated["title"] == "Late Song Updated"
    assert updated["youtube_id"] == "9bZkp7q19f0"

