import io


def login(client):
    username = client.application.config["ADMIN_USERNAME"]
    password = client.application.config["ADMIN_PASSWORD"]
    return client.post(
        "/admin/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def test_github_research_page_renders_two_cards(app, client):
    db = app.extensions["mongo_db"]
    db.github_research_items.insert_many(
        [
            {
                "kind": "repository",
                "title": "Portfolio App",
                "url": "https://github.com/example/portfolio",
                "description": "Main project",
                "sort_order": 1,
                "is_published": True,
            },
            {
                "kind": "research_pdf",
                "title": "ML Paper",
                "url": "https://example.com/papers/ml-paper.pdf",
                "description": "Research notes",
                "sort_order": 1,
                "is_published": True,
            },
        ]
    )

    response = client.get("/github-research")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Repositories" in html
    assert "Research PDFs" in html
    assert "View on GitHub" in html
    assert "Open PDF" in html


def test_admin_github_research_create_update_delete(app, client):
    db = app.extensions["mongo_db"]
    login_response = login(client)
    assert login_response.status_code == 302

    create_response = client.post(
        "/admin/github-research",
        data={
            "kind": "repository",
            "title": "New Repo",
            "url": "https://github.com/example/new-repo",
            "description": "first",
            "sort_order": "2",
            "is_published": "1",
        },
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    created = db.github_research_items.find_one({"title": "New Repo"})
    assert created is not None
    assert created["kind"] == "repository"

    update_response = client.post(
        f"/admin/github-research/{created['_id']}",
        data={
            "kind": "research_pdf",
            "title": "New Repo Updated",
            "url": "https://example.com/updated.pdf",
            "description": "updated",
            "sort_order": "5",
            "is_published": "1",
        },
        follow_redirects=False,
    )
    assert update_response.status_code == 302

    updated = db.github_research_items.find_one({"_id": created["_id"]})
    assert updated is not None
    assert updated["kind"] == "research_pdf"
    assert updated["title"] == "New Repo Updated"

    delete_response = client.post(f"/admin/github-research/{created['_id']}/delete", follow_redirects=False)
    assert delete_response.status_code == 302
    assert db.github_research_items.find_one({"_id": created["_id"]}) is None


def test_admin_github_research_pdf_upload(app, client):
    db = app.extensions["mongo_db"]
    login_response = login(client)
    assert login_response.status_code == 302

    create_response = client.post(
        "/admin/github-research",
        data={
            "kind": "research_pdf",
            "title": "Uploaded PDF",
            "description": "stored in mongo",
            "sort_order": "1",
            "is_published": "1",
            "pdf_file": (io.BytesIO(b"%PDF-1.4\n%fake"), "sample.pdf", "application/pdf"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert create_response.status_code == 302

    created = db.github_research_items.find_one({"title": "Uploaded PDF"})
    assert created is not None
    assert created["url"].startswith("/media/research-pdf/")
    assert created["storage_public_id"].startswith("mongo:")

    pdf_response = client.get(created["url"])
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
