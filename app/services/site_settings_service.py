from __future__ import annotations

from ..repositories.site_settings_repo import SiteSettingsRepository

HOME_NOTICE_BANNER_KEY = "home_notice_banner_text"
DEFAULT_HOME_NOTICE_BANNER_TEXT = "this should be something fun for those willing to read"
MAX_NOTICE_BANNER_LENGTH = 240


class SiteSettingsService:
    def __init__(self, db):
        self.repo = SiteSettingsRepository(db)

    def get_home_notice_banner_text(self) -> str:
        if not self.repo.available():
            return DEFAULT_HOME_NOTICE_BANNER_TEXT

        setting = self.repo.get_setting(HOME_NOTICE_BANNER_KEY) or {}
        value = setting.get("value")
        if not isinstance(value, str):
            return DEFAULT_HOME_NOTICE_BANNER_TEXT

        text = value.strip()
        return text or DEFAULT_HOME_NOTICE_BANNER_TEXT

    def update_home_notice_banner_text(self, raw_text: str | None) -> str:
        if not self.repo.available():
            raise RuntimeError("MongoDB is required for settings management")

        text = (raw_text or "").strip()
        if not text:
            raise ValueError("Notice banner text is required")
        if len(text) > MAX_NOTICE_BANNER_LENGTH:
            raise ValueError(f"Notice banner text must be {MAX_NOTICE_BANNER_LENGTH} characters or fewer")

        setting = self.repo.upsert_setting(HOME_NOTICE_BANNER_KEY, text) or {}
        return (setting.get("value") or "").strip()
