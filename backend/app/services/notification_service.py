"""In-app notification helpers."""
from typing import Optional

from app.core.database import db
from app.utils.ids import new_id, now_iso


async def create_notification(*, workspace_id: str, user_id: str, title: str, body: str,
                              kind: str, entity_type: Optional[str] = None,
                              entity_id: Optional[str] = None) -> None:
    await db.notifications.insert_one({
        "id": new_id(),
        "workspace_id": workspace_id,
        "user_id": user_id,
        "title": title,
        "body": body,
        "kind": kind,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "read": False,
        "created_at": now_iso(),
    })


async def notify_workspace(workspace_id: str, exclude_user: str, title: str, body: str,
                           kind: str, entity_type: Optional[str] = None,
                           entity_id: Optional[str] = None) -> None:
    members = await db.memberships.find(
        {"workspace_id": workspace_id, "user_id": {"$ne": exclude_user}}, {"_id": 0}
    ).to_list(500)
    for m in members:
        await create_notification(
            workspace_id=workspace_id, user_id=m["user_id"], title=title, body=body,
            kind=kind, entity_type=entity_type, entity_id=entity_id,
        )
