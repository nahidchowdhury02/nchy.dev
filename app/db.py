import certifi

from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

from flask import current_app


def init_db(app):
    uri = app.config.get("MONGODB_URI", "")
    db_name = app.config.get("MONGODB_DB_NAME", "archive")

    if not uri:
        app.logger.warning("MONGODB_URI is not set. MongoDB-backed features are unavailable.")
        app.extensions["mongo_client"] = None
        app.extensions["mongo_db"] = None
        return

    try:
        client_options = {
            "server_api": ServerApi("1"),
            "connectTimeoutMS": app.config.get("MONGODB_CONNECT_TIMEOUT_MS", 20000),
            "socketTimeoutMS": app.config.get("MONGODB_SOCKET_TIMEOUT_MS", 20000),
            "serverSelectionTimeoutMS": app.config.get("MONGODB_SERVER_SELECTION_TIMEOUT_MS", 30000),
        }

        if app.config.get("MONGODB_TLS", True):
            ca_file = app.config.get("MONGODB_TLS_CA_FILE") or certifi.where()
            client_options.update(
                {
                    "tls": True,
                    "tlsCAFile": ca_file,
                }
            )

        client = MongoClient(uri, **client_options)
        client.admin.command("ping")
        db = client[db_name]

        app.extensions["mongo_client"] = client
        app.extensions["mongo_db"] = db
        ensure_indexes(db)
        app.logger.info("Connected to MongoDB database '%s'", db_name)
    except PyMongoError as exc:
        app.logger.exception("Unable to connect to MongoDB: %s", exc)
        app.extensions["mongo_client"] = None
        app.extensions["mongo_db"] = None


def get_db():
    return current_app.extensions.get("mongo_db")


def db_is_ready() -> bool:
    return get_db() is not None


def ensure_indexes(db):
    db.books.create_index([("slug", ASCENDING)], unique=True)
    db.books.create_index([("title", TEXT), ("authors", TEXT)], name="books_text_search")
    db.books.create_index([("updated_at", DESCENDING)])
    db.reading_list.create_index([("book_id", ASCENDING)], unique=True)
    db.reading_list.create_index([("created_at", DESCENDING)])

    db.gallery_items.create_index([("category", ASCENDING), ("sort_order", ASCENDING)])
    db.gallery_items.create_index([("is_published", ASCENDING)])
    db.music_links.create_index([("sort_order", ASCENDING), ("created_at", DESCENDING)])
    db.music_links.create_index([("is_published", ASCENDING)])

    db.admin_users.create_index([("username", ASCENDING)], unique=True)

    db.audit_logs.create_index([("timestamp", DESCENDING)])
    db.audit_logs.create_index([("action", ASCENDING), ("timestamp", DESCENDING)])
    db.notes_logs.create_index([("created_at", DESCENDING)])
    db.notes_logs.create_index([("is_published", ASCENDING)])
    db.site_settings.create_index([("key", ASCENDING)], unique=True)
