from __future__ import annotations

from passlib.hash import pbkdf2_sha256

from ..repositories.admin_repo import AdminRepository
from ..repositories.audit_repo import AuditRepository


class AuthService:
    def __init__(self, db):
        self.admin_repo = AdminRepository(db)
        self.audit_repo = AuditRepository(db)

    def available(self) -> bool:
        return self.admin_repo.available()

    def authenticate_admin(self, username: str, password: str):
        user = self.admin_repo.get_by_username(username)
        if not user or not user.get("is_active", True):
            return None

        password_hash = user.get("password_hash")
        if not password_hash or not pbkdf2_sha256.verify(password, password_hash):
            return None

        self.admin_repo.touch_last_login(username)
        self.audit_repo.log(
            actor=username,
            action="auth.login",
            entity="admin_user",
            entity_id=user.get("id", ""),
        )
        return user

    def bootstrap_admin(self, username: str, password: str):
        if not self.admin_repo.available():
            raise RuntimeError("MongoDB is required for bootstrapping admin users")

        password_hash = pbkdf2_sha256.hash(password)
        user = self.admin_repo.upsert_admin(username=username, password_hash=password_hash)

        self.audit_repo.log(
            actor=username,
            action="auth.bootstrap",
            entity="admin_user",
            entity_id=user.get("id", ""),
        )

        return user
