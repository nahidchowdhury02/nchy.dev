from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_FILE = BASE_DIR / "static" / "data" / "books.json"


def load_books():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_books(books):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2)
