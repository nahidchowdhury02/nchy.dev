import mongomock
import pytest

from app import create_app
from app.config import TestConfig
from app.db import ensure_indexes
from app.services.auth_service import AuthService


class MongoTestConfig(TestConfig):
    SECRET_KEY = "test-secret"
    MONGODB_URI = ""
    MONGODB_DB_NAME = "archive_test"


@pytest.fixture
def app():
    flask_app = create_app(MongoTestConfig)

    mongo_db = mongomock.MongoClient().archive_test
    ensure_indexes(mongo_db)

    flask_app.extensions["mongo_db"] = mongo_db
    flask_app.extensions["mongo_client"] = None

    with flask_app.app_context():
        AuthService(mongo_db).bootstrap_admin("admin", "password123")

    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()
