"""Notification list + read markers."""
from fastapi import APIRouter, Depends

from app.core.database import db
from app.dependencies.tenant import require_workspace

router = APIRouter()


@router.get("/notifications")
async def list_notifications(ctx: dict = Depends(require_workspace)):
    q = {"workspace_id": ctx["workspace_id"], "user_id": ctx["user"]["id"]}
    docs = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)
    unread = await db.notifications.count_documents({**q, "read": False})
    return {"items": docs, "unread": unread}


@router.post("/notifications/{nid}/read")
async def mark_notification_read(nid: str, ctx: dict = Depends(require_workspace)):
    await db.notifications.update_one(
        {"id": nid, "workspace_id": ctx["workspace_id"], "user_id": ctx["user"]["id"]},
        {"$set": {"read": True}},
    )
    return {"ok": True}


@router.post("/notifications/read-all")
async def mark_all_read(ctx: dict = Depends(require_workspace)):
    await db.notifications.update_many(
        {"workspace_id": ctx["workspace_id"], "user_id": ctx["user"]["id"], "read": False},
        {"$set": {"read": True}},
    )
    return {"ok": True}
