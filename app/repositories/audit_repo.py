from __future__ import annotations

from datetime import datetime, timezone


class AuditRepository:
    def __init__(self, db):
        self.collection = db.audit_logs if db is not None else None

    def log(self, actor: str, action: str, entity: str, entity_id: str = "", metadata: dict | None = None):
        if not self.collection:
            return

        self.collection.insert_one(
            {
                "actor": actor,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "timestamp": datetime.now(timezone.utc),
                "metadata": metadata or {},
            }
        )
