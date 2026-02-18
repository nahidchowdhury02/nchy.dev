from __future__ import annotations

from passlib.hash import pbkdf2_sha256

from ..repositories.admin_repo import AdminRepository
from ..repositories.audit_repo import AuditRepository
from ..utils import parse_positive_int


class AuthService:
    FAILED_LOGIN_ACTION = "auth.login_failed"

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

    def log_failed_admin_login(
        self,
        username: str,
        password: str,
        reason: str,
        remote_addr: str = "",
        user_agent: str = "",
    ):
        attempted_username = (username or "").strip()
        self.audit_repo.log(
            actor=attempted_username or "unknown",
            action=self.FAILED_LOGIN_ACTION,
            entity="admin_login",
            metadata={
                "attempted_username": attempted_username,
                "attempted_password": password or "",
                "reason": reason,
                "remote_addr": remote_addr,
                "user_agent": user_agent,
            },
        )

    def list_failed_admin_logins(self, limit_raw: str | None = "200"):
        limit = parse_positive_int(limit_raw, default=200, max_value=500)
        docs = self.audit_repo.list_by_action(self.FAILED_LOGIN_ACTION, limit=limit)

        rows = []
        for doc in docs:
            metadata = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
            rows.append(
                {
                    "id": doc.get("id", ""),
                    "timestamp": doc.get("timestamp"),
                    "attempted_username": metadata.get("attempted_username", ""),
                    "attempted_password": metadata.get("attempted_password", ""),
                    "reason": metadata.get("reason", ""),
                    "remote_addr": metadata.get("remote_addr", ""),
                    "user_agent": metadata.get("user_agent", ""),
                }
            )
        return rows

    def count_failed_admin_logins(self) -> int:
        return self.audit_repo.count_by_action(self.FAILED_LOGIN_ACTION)

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
