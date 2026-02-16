from app.services.books_service import BooksService
from app.utils import extract_year


def test_extract_year_from_mixed_input():
    assert extract_year("Published in 1997") == 1997
    assert extract_year("2020-05-01") == 2020
    assert extract_year("unknown") is None


def test_normalize_source_book_with_google_info():
    service = BooksService(db=None)
    normalized = service.normalize_source_book(
        {
            "original_title": "The New Jim Crow michelle alexander",
            "google_info": {
                "title": "The New Jim Crow",
                "subtitle": "Mass Incarceration in the Age of Colorblindness",
                "authors": ["Michelle Alexander"],
                "publishedDate": "2012",
                "description": "desc",
            },
            "openlib_cover_url": "https://example.com/cover.jpg",
        }
    )

    assert normalized["title"] == "The New Jim Crow"
    assert normalized["authors"] == ["Michelle Alexander"]
    assert normalized["first_publish_year"] == 2012
    assert normalized["cover_url"] == "https://example.com/cover.jpg"


def test_normalize_source_book_handles_no_result_and_slug_uniqueness():
    service = BooksService(db=None)
    used_slugs = set()

    one = service.normalize_source_book(
        {
            "original_title": "A Title",
            "google_info": "No result",
            "openlib_cover_url": "No cover available",
        },
        used_slugs=used_slugs,
    )
    two = service.normalize_source_book(
        {
            "original_title": "A Title",
            "google_info": "No result",
            "openlib_cover_url": "No cover available",
        },
        used_slugs=used_slugs,
    )

    assert one["google_info"] is None
    assert one["cover_url"] is None
    assert one["slug"] == "a-title"
    assert two["slug"].startswith("a-title-")
