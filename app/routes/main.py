from flask import Blueprint, render_template, request, redirect

from ..services.books import load_books, save_books

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    return render_template("pages/index.html")


@main_bp.route("/gallery")
def gallery():
    return render_template("pages/gallery.html")


@main_bp.route("/gallery/sketches")
def gallery_sketches():
    return render_template("pages/gallery_sketches.html")


@main_bp.route("/gallery/moments")
def gallery_moments():
    return render_template("pages/gallery_moments.html")


@main_bp.route("/gallery/all")
def gallery_all():
    return render_template("pages/gallery_all.html")


@main_bp.route("/edit", methods=["GET", "POST"])
def edit():
    books = load_books()
    search_query = request.args.get("search", "").strip()
    book_to_edit = None

    if search_query:
        for book in books:
            if search_query.lower() in book["title"].lower():
                book_to_edit = book
                break

    if request.method == "POST":
        title = request.form["title"]
        for book in books:
            if book["title"] == title:
                book["author"] = request.form["author"]
                book["subtitle"] = request.form["subtitle"]
                book["first_publish_year"] = int(request.form["first_publish_year"])
                book["cover_url"] = request.form["cover_url"]
                save_books(books)
                return redirect("/edit?search=" + title)

    return render_template("pages/edit.html", book=book_to_edit, query=search_query)
