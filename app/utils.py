import re
from typing import Any

from bson import ObjectId

_slug_pattern = re.compile(r"[^a-z0-9]+")
_year_pattern = re.compile(r"(1[5-9]\d{2}|20\d{2})")


def slugify(text: str) -> str:
    slug = _slug_pattern.sub("-", text.lower()).strip("-")
    return slug or "untitled"


def ensure_unique_slug(base_slug: str, used_slugs: set[str]) -> str:
    slug = base_slug
    suffix = 2
    while slug in used_slugs:
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    used_slugs.add(slug)
    return slug


def extract_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1500 <= value <= 2099 else None
    match = _year_pattern.search(str(value))
    if not match:
        return None
    return int(match.group(1))


def parse_positive_int(value: str | None, default: int, max_value: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    if parsed < 1:
        return default
    return min(parsed, max_value)


def maybe_object_id(value: str) -> ObjectId | None:
    if ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def serialize_doc(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    serialized = dict(document)
    if "_id" in serialized:
        serialized["_id"] = str(serialized["_id"])
        serialized["id"] = serialized["_id"]
    return serialized
