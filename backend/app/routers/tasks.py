"""Tasks CRUD."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.schemas.tasks import TaskIn
from app.services.notification_service import create_notification
from app.utils.ids import new_id, now_iso
from app.utils.pagination import clamp_limit, clamp_skip
from app.utils.tenant import (
    ensure_assignee_in_workspace,
    ensure_related_in_workspace,
    workspace_query,
)

router = APIRouter()


@router.get("/tasks")
async def list_tasks(status_filter: Optional[str] = None, page: int = 1, limit: int = 100,
                     ctx: dict = Depends(require_perm("task", "view"))):
    limit = clamp_limit(limit, default=100, maximum=100)
    skip = clamp_skip(page, limit)
    q = workspace_query(ctx)
    if status_filter:
        q["status"] = status_filter
    return await db.tasks.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)


@router.post("/tasks")
async def create_task(body: TaskIn, ctx: dict = Depends(require_perm("task", "create"))):
    await ensure_assignee_in_workspace(body.assignee_id, ctx["workspace_id"])
    await ensure_related_in_workspace(body.related_type, body.related_id, ctx["workspace_id"])
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.tasks.insert_one(doc)
    doc.pop("_id", None)
    if body.assignee_id and body.assignee_id != ctx["user"]["id"]:
        await create_notification(
            workspace_id=ctx["workspace_id"],
            user_id=body.assignee_id,
            title="New task assigned",
            body=f"{ctx['user']['name']} assigned you: {body.title}",
            kind="task_assigned",
            entity_type="task",
            entity_id=doc["id"],
        )
    return doc


@router.put("/tasks/{tid}")
async def update_task(tid: str, body: TaskIn, ctx: dict = Depends(require_perm("task", "edit"))):
    await ensure_assignee_in_workspace(body.assignee_id, ctx["workspace_id"])
    await ensure_related_in_workspace(body.related_type, body.related_id, ctx["workspace_id"])
    r = await db.tasks.update_one(
        workspace_query(ctx, {"id": tid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}


@router.delete("/tasks/{tid}")
async def delete_task(tid: str, ctx: dict = Depends(require_perm("task", "delete"))):
    r = await db.tasks.delete_one(workspace_query(ctx, {"id": tid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    return {"ok": True}
