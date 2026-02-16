from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pymongo import MongoClient
from pymongo.server_api import ServerApi

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import ensure_indexes  # noqa: E402
from app.services.books_service import BooksService  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Import static/data/books.json into MongoDB")
    parser.add_argument(
        "--input",
        default=str(ROOT_DIR / "static" / "data" / "books.json"),
        help="Path to source books JSON file",
    )
    parser.add_argument("--mongo-uri", default=os.getenv("MONGODB_URI", ""), help="MongoDB connection URI")
    parser.add_argument(
        "--db-name",
        default=os.getenv("MONGODB_DB_NAME", "archive"),
        help="MongoDB database name",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing")
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.mongo_uri:
        raise SystemExit("Missing --mongo-uri or MONGODB_URI")

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as handle:
        raw_books = json.load(handle)

    client = MongoClient(args.mongo_uri, server_api=ServerApi("1"))
    client.admin.command("ping")
    db = client[args.db_name]
    ensure_indexes(db)

    books_collection = db.books

    existing_slugs = set(books_collection.distinct("slug"))
    used_slugs = set(existing_slugs)

    books_service = BooksService(db=None)

    migrated = 0
    updated = 0
    skipped = 0
    errors = 0

    for index, raw_book in enumerate(raw_books, start=1):
        try:
            normalized = books_service.normalize_source_book(raw_book, used_slugs=used_slugs)
            existing = books_collection.find_one(
                {"original_title": normalized["original_title"]},
                {"_id": 1, "slug": 1},
            )
            if existing and existing.get("slug"):
                normalized["slug"] = existing["slug"]
                used_slugs.add(existing["slug"])

            original_title = normalized["original_title"]
            created_at = normalized.pop("created_at")

            if args.dry_run:
                if existing:
                    updated += 1
                else:
                    migrated += 1
                continue

            result = books_collection.update_one(
                {"original_title": original_title},
                {
                    "$set": normalized,
                    "$setOnInsert": {"created_at": created_at},
                },
                upsert=True,
            )

            if result.upserted_id:
                migrated += 1
            elif result.modified_count:
                updated += 1
            else:
                skipped += 1

        except Exception as exc:
            errors += 1
            print(f"[{index}] error: {exc}")

    print("Migration complete")
    print(f"- source_rows: {len(raw_books)}")
    print(f"- migrated: {migrated}")
    print(f"- updated: {updated}")
    print(f"- skipped: {skipped}")
    print(f"- errors: {errors}")
    print(f"- dry_run: {args.dry_run}")


if __name__ == "__main__":
    main()
