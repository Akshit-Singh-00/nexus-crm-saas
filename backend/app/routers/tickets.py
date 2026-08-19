"""Support tickets CRUD + stats."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.schemas.tickets import TicketIn
from app.services.audit_service import audit
from app.services.notification_service import create_notification
from app.utils.ids import new_id, now_iso
from app.utils.pagination import clamp_limit, clamp_skip
from app.utils.tenant import (
    ensure_assignee_in_workspace,
    ensure_customer_in_workspace,
    workspace_query,
)

router = APIRouter()


def _next_ticket_number(seq: int) -> str:
    return f"TKT-{seq:05d}"


@router.get("/tickets")
async def list_tickets(status_filter: Optional[str] = None, page: int = 1, limit: int = 100,
                       ctx: dict = Depends(require_perm("ticket", "view"))):
    limit = clamp_limit(limit, default=100, maximum=100)
    skip = clamp_skip(page, limit)
    q = workspace_query(ctx)
    if status_filter:
        q["status"] = status_filter
    return await db.tickets.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)


@router.post("/tickets")
async def create_ticket(body: TicketIn, ctx: dict = Depends(require_perm("ticket", "create"))):
    await ensure_customer_in_workspace(body.customer_id, ctx["workspace_id"])
    await ensure_assignee_in_workspace(body.assignee_id, ctx["workspace_id"])
    count = await db.tickets.count_documents({"workspace_id": ctx["workspace_id"]})
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "number": _next_ticket_number(count + 1),
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.tickets.insert_one(doc)
    await audit(ctx, "created", "ticket", doc["id"], after={"subject": body.subject})
    if body.assignee_id and body.assignee_id != ctx["user"]["id"]:
        await create_notification(
            workspace_id=ctx["workspace_id"], user_id=body.assignee_id,
            title=f"Ticket {doc['number']} assigned",
            body=f"{ctx['user']['name']} assigned you a ticket: {body.subject}",
            kind="ticket_assigned", entity_type="ticket", entity_id=doc["id"],
        )
    doc.pop("_id", None)
    return doc


@router.get("/tickets/stats/overview")
async def ticket_stats(ctx: dict = Depends(require_perm("ticket", "view"))):
    wid = ctx["workspace_id"]
    open_ = await db.tickets.count_documents({"workspace_id": wid, "status": {"$nin": ["resolved", "closed"]}})
    resolved = await db.tickets.count_documents({"workspace_id": wid, "status": "resolved"})
    high_pri = await db.tickets.count_documents({"workspace_id": wid, "priority": {"$in": ["high", "urgent"]}, "status": {"$nin": ["resolved", "closed"]}})
    total = await db.tickets.count_documents({"workspace_id": wid})
    return {"open": open_, "resolved": resolved, "high_priority": high_pri, "total": total}


@router.get("/tickets/{tid}")
async def get_ticket(tid: str, ctx: dict = Depends(require_perm("ticket", "view"))):
    doc = await db.tickets.find_one(workspace_query(ctx, {"id": tid}), {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@router.put("/tickets/{tid}")
async def update_ticket(tid: str, body: TicketIn, ctx: dict = Depends(require_perm("ticket", "edit"))):
    await ensure_customer_in_workspace(body.customer_id, ctx["workspace_id"])
    await ensure_assignee_in_workspace(body.assignee_id, ctx["workspace_id"])
    before = await db.tickets.find_one(workspace_query(ctx, {"id": tid}), {"_id": 0})
    if not before:
        raise HTTPException(404, "Not found")
    await db.tickets.update_one(
        workspace_query(ctx, {"id": tid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    payload = body.model_dump()
    changed = {k: payload[k] for k in payload if before.get(k) != payload[k]}
    await audit(ctx, "updated", "ticket", tid,
                before={k: before.get(k) for k in changed}, after=changed)
    return {"ok": True}


@router.delete("/tickets/{tid}")
async def delete_ticket(tid: str, ctx: dict = Depends(require_perm("ticket", "delete"))):
    before = await db.tickets.find_one(workspace_query(ctx, {"id": tid}), {"_id": 0})
    r = await db.tickets.delete_one(workspace_query(ctx, {"id": tid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await audit(ctx, "deleted", "ticket", tid, before=before)
    return {"ok": True}
