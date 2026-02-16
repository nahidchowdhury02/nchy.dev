from flask import Blueprint, abort, jsonify, request

from ..db import get_db
from ..services.books_service import BooksService
from ..services.gallery_service import GalleryService

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/books")
def books_list():
    books_service = BooksService(get_db())
    query = request.args.get("query", "").strip()
    cursor = request.args.get("cursor")
    limit_raw = request.args.get("limit")

    items, next_cursor = books_service.list_public_books(query=query, limit_raw=limit_raw, cursor=cursor)
    return jsonify({"items": items, "next_cursor": next_cursor})


@api_bp.route("/books/<id_or_slug>")
def books_detail(id_or_slug):
    books_service = BooksService(get_db())
    book = books_service.get_public_book(id_or_slug)
    if not book:
        abort(404, description="Book not found")
    return jsonify(book)


@api_bp.route("/gallery")
def gallery_list():
    gallery_service = GalleryService(get_db())

    category = request.args.get("category", "all")
    cursor = request.args.get("cursor")
    limit_raw = request.args.get("limit")

    items, next_cursor = gallery_service.list_public_items(
        category=category,
        limit_raw=limit_raw,
        cursor=cursor,
    )
    return jsonify({"items": items, "next_cursor": next_cursor})
