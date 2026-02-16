from app import create_app
from app.config import Config


class CsrfConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    MONGODB_URI = ""
    WTF_CSRF_ENABLED = True
    ADMIN_USERNAME = "admin_test"
    ADMIN_PASSWORD = "password123_test"


def test_login_requires_csrf_when_enabled():
    app = create_app(CsrfConfig)
    client = app.test_client()

    response = client.post(
        "/admin/login",
        data={"username": CsrfConfig.ADMIN_USERNAME, "password": CsrfConfig.ADMIN_PASSWORD},
        follow_redirects=False,
    )

    assert response.status_code == 400
