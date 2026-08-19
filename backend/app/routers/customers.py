"""Customers CRUD."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.schemas.customers import CustomerIn
from app.services.audit_service import audit, log_activity
from app.services.workflow_service import fire_workflows
from app.utils.ids import new_id, now_iso
from app.utils.pagination import clamp_limit, clamp_skip
from app.utils.tenant import escape_regex, workspace_query

router = APIRouter()


@router.get("/customers")
async def list_customers(search: str = "", page: int = 1, limit: int = 100,
                         ctx: dict = Depends(require_perm("customer", "view"))):
    limit = clamp_limit(limit, default=100, maximum=100)
    skip = clamp_skip(page, limit)
    q = workspace_query(ctx)
    if search:
        rx = {"$regex": escape_regex(search), "$options": "i"}
        q["$or"] = [{"name": rx}, {"email": rx}, {"company": rx}]
    return await db.customers.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)


@router.post("/customers")
async def create_customer(body: CustomerIn, ctx: dict = Depends(require_perm("customer", "create"))):
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.customers.insert_one(doc)
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "created", "customer", doc["id"], {"name": body.name})
    await fire_workflows("customer_created", ctx["workspace_id"], doc)
    doc.pop("_id", None)
    return doc


@router.get("/customers/{cid}")
async def get_customer(cid: str, ctx: dict = Depends(require_perm("customer", "view"))):
    doc = await db.customers.find_one(workspace_query(ctx, {"id": cid}), {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@router.put("/customers/{cid}")
async def update_customer(cid: str, body: CustomerIn, ctx: dict = Depends(require_perm("customer", "edit"))):
    r = await db.customers.update_one(
        workspace_query(ctx, {"id": cid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "updated", "customer", cid)
    await audit(ctx, "updated", "customer", cid, after={"name": body.name})
    return {"ok": True}


@router.delete("/customers/{cid}")
async def delete_customer(cid: str, ctx: dict = Depends(require_perm("customer", "delete"))):
    before = await db.customers.find_one(workspace_query(ctx, {"id": cid}), {"_id": 0})
    r = await db.customers.delete_one(workspace_query(ctx, {"id": cid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "deleted", "customer", cid)
    await audit(ctx, "deleted", "customer", cid, before=before)
    return {"ok": True}
