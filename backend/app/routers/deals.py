"""Deals CRUD + kanban stage update."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.schemas.deals import DealIn, DealStageUpdate
from app.services.audit_service import log_activity
from app.services.deal_service import compute_deal_risk
from app.services.notification_service import notify_workspace
from app.services.workflow_service import fire_workflows
from app.utils.ids import new_id, now_iso
from app.utils.pagination import clamp_limit, clamp_skip
from app.utils.tenant import (
    ensure_assignee_in_workspace,
    ensure_customer_in_workspace,
    workspace_query,
)

router = APIRouter()


@router.get("/deals")
async def list_deals(page: int = 1, limit: int = 100,
                     ctx: dict = Depends(require_perm("deal", "view"))):
    limit = clamp_limit(limit, default=100, maximum=100)
    skip = clamp_skip(page, limit)
    deals = await db.deals.find(workspace_query(ctx), {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    for d in deals:
        d["risk"] = compute_deal_risk(d)
    return deals


@router.post("/deals")
async def create_deal(body: DealIn, ctx: dict = Depends(require_perm("deal", "create"))):
    await ensure_customer_in_workspace(body.customer_id, ctx["workspace_id"])
    await ensure_assignee_in_workspace(body.assignee_id, ctx["workspace_id"])
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.deals.insert_one(doc)
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "created", "deal", doc["id"], {"title": body.title})
    await fire_workflows("deal_created", ctx["workspace_id"], doc)
    doc.pop("_id", None)
    return doc


@router.put("/deals/{did}")
async def update_deal(did: str, body: DealIn, ctx: dict = Depends(require_perm("deal", "edit"))):
    await ensure_customer_in_workspace(body.customer_id, ctx["workspace_id"])
    await ensure_assignee_in_workspace(body.assignee_id, ctx["workspace_id"])
    r = await db.deals.update_one(
        workspace_query(ctx, {"id": did}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "updated", "deal", did)
    return {"ok": True}


@router.patch("/deals/{did}/stage")
async def update_deal_stage(did: str, body: DealStageUpdate, ctx: dict = Depends(require_perm("deal", "edit"))):
    r = await db.deals.update_one(
        workspace_query(ctx, {"id": did}),
        {"$set": {"stage": body.stage, "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "stage_changed", "deal", did, {"stage": body.stage})
    updated = await db.deals.find_one(workspace_query(ctx, {"id": did}), {"_id": 0})
    if updated:
        await fire_workflows("deal_stage_changed", ctx["workspace_id"], updated)
    await notify_workspace(
        ctx["workspace_id"],
        exclude_user=ctx["user"]["id"],
        title=f"Deal moved to {body.stage}",
        body=f"{ctx['user']['name']} moved a deal to {body.stage}.",
        kind="deal_stage",
        entity_type="deal",
        entity_id=did,
    )
    return {"ok": True}


@router.delete("/deals/{did}")
async def delete_deal(did: str, ctx: dict = Depends(require_perm("deal", "delete"))):
    r = await db.deals.delete_one(workspace_query(ctx, {"id": did}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "deleted", "deal", did)
    return {"ok": True}
