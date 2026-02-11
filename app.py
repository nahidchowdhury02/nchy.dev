from flask import Flask, render_template, request, redirect
import json
import os

app = Flask(__name__)

DATA_FILE = "static/data/books.json"

def load_books():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_books(books):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2)


# --- Routes ---
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/edit", methods=["GET", "POST"])
def edit():
    books = load_books()
    search_query = request.args.get("search", "").strip()
    book_to_edit = None

    # Search
    if search_query:
        for book in books:
            if search_query.lower() in book["title"].lower():
                book_to_edit = book
                break

    # Update
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

    return render_template("edit.html", book=book_to_edit, query=search_query)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
