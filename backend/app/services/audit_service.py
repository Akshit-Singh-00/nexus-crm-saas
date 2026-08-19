"""Audit + activity write helpers."""
from typing import Optional

from app.core.database import db
from app.utils.ids import new_id, now_iso


async def audit(ctx: dict, action: str, resource: str, resource_id: str,
                before: Optional[dict] = None, after: Optional[dict] = None) -> None:
    await db.audit_logs.insert_one({
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "user_id": ctx["user"]["id"],
        "user_email": ctx["user"].get("email"),
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "before": before,
        "after": after,
        "created_at": now_iso(),
    })


async def log_activity(workspace_id: str, actor_id: str, action: str,
                       entity_type: str, entity_id: str,
                       meta: Optional[dict] = None) -> None:
    await db.activities.insert_one({
        "id": new_id(),
        "workspace_id": workspace_id,
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "meta": meta or {},
        "created_at": now_iso(),
    })


async def audit_auth_event(user_id: Optional[str], user_email: Optional[str],
                           action: str, resource_id: str) -> None:
    """Login-success / login-failed audit rows (workspace_id is None for auth events)."""
    await db.audit_logs.insert_one({
        "id": new_id(),
        "workspace_id": None,
        "user_id": user_id,
        "user_email": user_email,
        "action": action,
        "resource": "auth",
        "resource_id": resource_id,
        "created_at": now_iso(),
    })
