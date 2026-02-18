from __future__ import annotations

from datetime import datetime, timezone

from pymongo import DESCENDING

from ..utils import serialize_doc


class AuditRepository:
    def __init__(self, db):
        self.collection = db.audit_logs if db is not None else None

    def log(self, actor: str, action: str, entity: str, entity_id: str = "", metadata: dict | None = None):
        if self.collection is None:
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

    def list_by_action(self, action: str, limit: int = 200):
        if self.collection is None:
            return []
        docs = self.collection.find({"action": action}).sort("timestamp", DESCENDING).limit(limit)
        return [serialize_doc(doc) for doc in docs]

    def count_by_action(self, action: str) -> int:
        if self.collection is None:
            return 0
        return self.collection.count_documents({"action": action})
