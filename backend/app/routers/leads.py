"""Leads CRUD."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.schemas.leads import LeadIn
from app.services.audit_service import log_activity
from app.services.workflow_service import fire_workflows
from app.utils.ids import new_id, now_iso
from app.utils.pagination import clamp_limit, clamp_skip
from app.utils.tenant import escape_regex, workspace_query

router = APIRouter()


@router.get("/leads")
async def list_leads(search: str = "", page: int = 1, limit: int = 100,
                     ctx: dict = Depends(require_perm("lead", "view"))):
    limit = clamp_limit(limit, default=100, maximum=100)
    skip = clamp_skip(page, limit)
    q = workspace_query(ctx)
    if search:
        rx = {"$regex": escape_regex(search), "$options": "i"}
        q["$or"] = [{"name": rx}, {"email": rx}, {"company": rx}]
    return await db.leads.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)


@router.post("/leads")
async def create_lead(body: LeadIn, ctx: dict = Depends(require_perm("lead", "create"))):
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "score": None,
        "score_reason": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.leads.insert_one(doc)
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "created", "lead", doc["id"], {"name": body.name})
    await fire_workflows("lead_created", ctx["workspace_id"], doc)
    doc.pop("_id", None)
    return doc


@router.put("/leads/{lid}")
async def update_lead(lid: str, body: LeadIn, ctx: dict = Depends(require_perm("lead", "edit"))):
    r = await db.leads.update_one(
        workspace_query(ctx, {"id": lid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "updated", "lead", lid)
    return {"ok": True}


@router.delete("/leads/{lid}")
async def delete_lead(lid: str, ctx: dict = Depends(require_perm("lead", "delete"))):
    r = await db.leads.delete_one(workspace_query(ctx, {"id": lid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "deleted", "lead", lid)
    return {"ok": True}
