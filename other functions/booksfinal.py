import json
import requests
import time
import os

INPUT_FILE = "data.txt"
OUTPUT_FILE = "google_results.json"

def fetch_google_data(title, author):
    """Query Google Books API using both title and author."""
    query = f"intitle:{requests.utils.quote(title)}+inauthor:{requests.utils.quote(author)}"
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if "items" in data and len(data["items"]) > 0:
            volume = data["items"][0]["volumeInfo"]
            search_info = data["items"][0].get("searchInfo", {})

            return {
                "title": volume.get("title"),
                "subtitle": volume.get("subtitle"),
                "authors": volume.get("authors"),
                "publishedDate": volume.get("publishedDate"),
                "categories": volume.get("categories"),
                "averageRating": volume.get("averageRating"),
                "ratingsCount": volume.get("ratingsCount"),
                "publisher": volume.get("publisher"),
                "pageCount": volume.get("pageCount"),
                "language": volume.get("language"),
                "description": volume.get("description"),
                "previewLink": volume.get("previewLink"),
                "infoLink": volume.get("infoLink"),
                "canonicalVolumeLink": volume.get("canonicalVolumeLink"),
                "industryIdentifiers": volume.get("industryIdentifiers"),
                "printType": volume.get("printType"),
                "contentVersion": volume.get("contentVersion"),
                "maturityRating": volume.get("maturityRating"),
                "textSnippet": search_info.get("textSnippet")
            }
    except Exception as e:
        print(f"Error fetching data from Google for '{title}' by '{author}': {e}")
    return None

def fetch_openlib_cover(title, author):
    """Fetch Open Library cover image URL using title and author."""
    query = f"{title} {author}".strip()
    url = "https://openlibrary.org/search.json"
    try:
        response = requests.get(url, params={"q": query, "limit": 1})
        response.raise_for_status()
        data = response.json()

        if data["docs"]:
            doc = data["docs"][0]
            if "cover_i" in doc:
                return f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg"
    except Exception as e:
        print(f"OpenLibrary error for '{title}': {e}")
    return "No cover available"

def load_existing_results():
    """Load already saved books (to avoid duplicates)."""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_results(results):
    """Save entire results to the output file."""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

def split_title_author(line):
    """Split title and author based on last two words assumed to be the author's name."""
    parts = line.strip().rsplit(" ", 2)
    if len(parts) == 3:
        title = parts[0]
        author = f"{parts[1]} {parts[2]}"
    else:
        title = line.strip()
        author = ""
    return title, author

def main():
    # Read lines from data.txt
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    results = load_existing_results()
    saved_titles = {entry["original_title"] for entry in results}

    for line in lines:
        title, author = split_title_author(line)
        original = f"{title} {author}".strip()

        if original in saved_titles:
            print(f"Skipping (already saved): {original}")
            continue

        print(f"Fetching: {title} by {author}")
        google_info = fetch_google_data(title, author)
        openlib_cover_url = fetch_openlib_cover(title, author)

        entry = {
            "original_title": original,
            "google_info": google_info if google_info else "No result",
            "openlib_cover_url": openlib_cover_url
        }

        results.append(entry)
        save_results(results)
        print(f"Saved: {original}\n")
        time.sleep(1)  # Respectful delay to Google Books API

if __name__ == "__main__":
    main()
