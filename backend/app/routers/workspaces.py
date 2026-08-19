"""Workspace CRUD + members + settings."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.auth import current_user
from app.dependencies.permissions import require_perm
from app.dependencies.tenant import require_workspace
from app.schemas.auth import MemberRoleIn
from app.schemas.workspace import WorkspaceIn, WorkspaceSettingsIn
from app.services.audit_service import audit
from app.services.deal_service import DEFAULT_PIPELINE_STAGES
from app.utils.ids import new_id, now_iso

router = APIRouter()


@router.post("/workspaces")
async def create_workspace(body: WorkspaceIn, user: dict = Depends(current_user)):
    wid = new_id()
    workspace = {
        "id": wid,
        "name": body.name,
        "industry": body.industry,
        "owner_id": user["id"],
        "plan": "starter",
        "logo_url": None,
        "pipeline_stages": DEFAULT_PIPELINE_STAGES,
        "created_at": now_iso(),
    }
    await db.workspaces.insert_one(workspace)
    await db.memberships.insert_one({
        "id": new_id(),
        "user_id": user["id"],
        "workspace_id": wid,
        "role": "owner",
        "created_at": now_iso(),
    })
    workspace.pop("_id", None)
    return {**workspace, "role": "owner"}


@router.get("/workspaces/members")
async def list_members(ctx: dict = Depends(require_workspace)):
    memberships = await db.memberships.find(
        {"workspace_id": ctx["workspace_id"]}, {"_id": 0}
    ).to_list(500)
    uids = [m["user_id"] for m in memberships]
    users = await db.users.find({"id": {"$in": uids}}, {"_id": 0, "password": 0}).to_list(500)
    umap = {u["id"]: u for u in users}
    return [
        {**umap.get(m["user_id"], {"id": m["user_id"]}), "role": m["role"], "membership_id": m["id"]}
        for m in memberships
    ]


@router.get("/workspaces/settings")
async def get_workspace_settings(ctx: dict = Depends(require_perm("settings", "view"))):
    ws = await db.workspaces.find_one({"id": ctx["workspace_id"]}, {"_id": 0})
    if not ws:
        raise HTTPException(404, "Workspace not found")
    if not ws.get("pipeline_stages"):
        ws["pipeline_stages"] = DEFAULT_PIPELINE_STAGES
    return ws


@router.put("/workspaces/settings")
async def update_workspace_settings(body: WorkspaceSettingsIn,
                                    ctx: dict = Depends(require_perm("settings", "manage"))):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if "pipeline_stages" in update:
        seen_ids = set()
        for s in update["pipeline_stages"]:
            if not s.get("id") or not s.get("label"):
                raise HTTPException(400, "Each stage needs id and label")
            if s["id"] in seen_ids:
                raise HTTPException(400, f"Duplicate stage id: {s['id']}")
            seen_ids.add(s["id"])
    if not update:
        return {"ok": True}
    before = await db.workspaces.find_one({"id": ctx["workspace_id"]}, {"_id": 0, "password": 0})
    await db.workspaces.update_one({"id": ctx["workspace_id"]},
                                   {"$set": {**update, "updated_at": now_iso()}})
    await audit(ctx, "updated", "workspace", ctx["workspace_id"],
                before={k: before.get(k) for k in update.keys()},
                after=update)
    return {"ok": True}


@router.patch("/workspaces/members/{user_id}/role")
async def update_member_role(user_id: str, body: MemberRoleIn,
                             ctx: dict = Depends(require_perm("member", "manage"))):
    target = await db.memberships.find_one(
        {"workspace_id": ctx["workspace_id"], "user_id": user_id}, {"_id": 0}
    )
    if not target:
        raise HTTPException(404, "Member not found")
    if target["role"] == "owner":
        raise HTTPException(403, "Cannot change the owner's role")
    if user_id == ctx["user"]["id"]:
        raise HTTPException(403, "Cannot change your own role")
    await db.memberships.update_one(
        {"workspace_id": ctx["workspace_id"], "user_id": user_id},
        {"$set": {"role": body.role}},
    )
    await audit(ctx, "role_changed", "member", user_id,
                before={"role": target["role"]}, after={"role": body.role})
    return {"ok": True}


@router.delete("/workspaces/members/{user_id}")
async def remove_member(user_id: str, ctx: dict = Depends(require_perm("member", "manage"))):
    target = await db.memberships.find_one(
        {"workspace_id": ctx["workspace_id"], "user_id": user_id}, {"_id": 0}
    )
    if not target:
        raise HTTPException(404, "Member not found")
    if target["role"] == "owner":
        raise HTTPException(403, "Cannot remove the owner")
    if user_id == ctx["user"]["id"]:
        raise HTTPException(403, "Cannot remove yourself")
    await db.memberships.delete_one({"workspace_id": ctx["workspace_id"], "user_id": user_id})
    await audit(ctx, "removed", "member", user_id, before=target)
    return {"ok": True}
