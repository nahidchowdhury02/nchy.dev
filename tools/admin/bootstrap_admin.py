from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from pymongo import MongoClient
from pymongo.server_api import ServerApi

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import ensure_indexes  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Create or update the single admin account")
    parser.add_argument("--username", required=True, help="Admin username")
    parser.add_argument("--password", default="", help="Admin password (leave empty to prompt securely)")
    parser.add_argument("--token", default="", help="Bootstrap token when ADMIN_BOOTSTRAP_TOKEN is set")
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI", ""), help="MongoDB connection URI")
    parser.add_argument(
        "--db-name",
        default=os.getenv("MONGODB_DB_NAME", "archive"),
        help="MongoDB database name",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    expected_token = os.getenv("ADMIN_BOOTSTRAP_TOKEN", "")
    if expected_token and args.token != expected_token:
        raise SystemExit("Invalid bootstrap token")

    if not args.mongo_uri:
        raise SystemExit("Missing --mongo-uri or MONGODB_URI")

    password = args.password or getpass.getpass("Admin password: ")
    if not password:
        raise SystemExit("Password is required")

    client = MongoClient(args.mongo_uri, server_api=ServerApi("1"))
    client.admin.command("ping")

    db = client[args.db_name]
    ensure_indexes(db)

    auth_service = AuthService(db)
    user = auth_service.bootstrap_admin(username=args.username, password=password)

    print("Admin user is ready")
    print(f"- username: {user['username']}")
    print(f"- id: {user['id']}")


if __name__ == "__main__":
    main()
