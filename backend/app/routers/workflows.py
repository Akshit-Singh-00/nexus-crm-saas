"""Workflow CRUD."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.schemas.workflows import WORKFLOW_TRIGGERS, WorkflowIn
from app.services.audit_service import audit
from app.services.workflow_service import validate_workflow_action_targets
from app.utils.ids import new_id, now_iso
from app.utils.tenant import workspace_query

router = APIRouter()


@router.get("/workflows")
async def list_workflows(ctx: dict = Depends(require_perm("settings", "manage"))):
    return await db.workflows.find(workspace_query(ctx), {"_id": 0}).sort("created_at", -1).to_list(100)


@router.post("/workflows")
async def create_workflow(body: WorkflowIn, ctx: dict = Depends(require_perm("settings", "manage"))):
    if body.trigger not in WORKFLOW_TRIGGERS:
        raise HTTPException(400, "Invalid trigger")
    await validate_workflow_action_targets(body.actions, ctx["workspace_id"])
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "run_count": 0,
        "last_run_at": None,
        **body.model_dump(),
    }
    await db.workflows.insert_one(doc)
    await audit(ctx, "created", "workflow", doc["id"], after={"name": body.name, "trigger": body.trigger})
    doc.pop("_id", None)
    return doc


@router.put("/workflows/{wid}")
async def update_workflow(wid: str, body: WorkflowIn, ctx: dict = Depends(require_perm("settings", "manage"))):
    await validate_workflow_action_targets(body.actions, ctx["workspace_id"])
    r = await db.workflows.update_one(
        workspace_query(ctx, {"id": wid}),
        {"$set": {**body.model_dump(), "updated_at": now_iso()}},
    )
    if not r.matched_count:
        raise HTTPException(404, "Not found")
    await audit(ctx, "updated", "workflow", wid, after={"name": body.name})
    return {"ok": True}


@router.delete("/workflows/{wid}")
async def delete_workflow(wid: str, ctx: dict = Depends(require_perm("settings", "manage"))):
    r = await db.workflows.delete_one(workspace_query(ctx, {"id": wid}))
    if not r.deleted_count:
        raise HTTPException(404, "Not found")
    await audit(ctx, "deleted", "workflow", wid)
    return {"ok": True}
