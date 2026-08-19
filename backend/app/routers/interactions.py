"""Emails, calls, meetings, files — unified as workspace-scoped `interactions`.

Each interaction is tagged with `kind` (email|call|meeting|file) and optionally
attached to a customer and/or a deal. All create endpoints validate cross-tenant
references and emit an audit + activity entry so they show up on the timeline.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.dependencies.tenant import require_workspace
from app.schemas.interactions import (
    CallLogIn,
    EmailLogIn,
    FileMetaIn,
    MeetingIn,
    MeetingStatusIn,
)
from app.services.audit_service import log_activity
from app.utils.ids import new_id, now_iso
from app.utils.pagination import clamp_limit, clamp_skip
from app.utils.tenant import (
    ensure_customer_in_workspace,
    ensure_deal_in_workspace,
    workspace_query,
)

router = APIRouter()

MAX_FILE_BYTES = 5 * 1024 * 1024   # 5 MB soft cap on inline files


async def _list_kind(kind: str, ctx: dict, customer_id: Optional[str], deal_id: Optional[str],
                     page: int, limit: int) -> list:
    limit = clamp_limit(limit, default=50, maximum=100)
    skip = clamp_skip(page, limit)
    q = workspace_query(ctx, {"kind": kind})
    if customer_id:
        q["customer_id"] = customer_id
    if deal_id:
        q["deal_id"] = deal_id
    return await db.interactions.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)


# ----------- EMAILS -----------
@router.get("/emails")
async def list_emails(customer_id: Optional[str] = None, deal_id: Optional[str] = None,
                      page: int = 1, limit: int = 50,
                      ctx: dict = Depends(require_workspace)):
    return await _list_kind("email", ctx, customer_id, deal_id, page, limit)


@router.post("/emails")
async def log_email(body: EmailLogIn, ctx: dict = Depends(require_workspace)):
    await ensure_customer_in_workspace(body.customer_id, ctx["workspace_id"])
    await ensure_deal_in_workspace(body.deal_id, ctx["workspace_id"])
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "kind": "email",
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.interactions.insert_one(doc)
    entity_type = "customer" if body.customer_id else ("deal" if body.deal_id else "workspace")
    entity_id = body.customer_id or body.deal_id or ctx["workspace_id"]
    await log_activity(ctx["workspace_id"], ctx["user"]["id"],
                       "sent_email" if body.direction == "outbound" else "received_email",
                       entity_type, entity_id, {"subject": body.subject})
    doc.pop("_id", None)
    return doc


# ----------- CALLS -----------
@router.get("/calls")
async def list_calls(customer_id: Optional[str] = None, deal_id: Optional[str] = None,
                     page: int = 1, limit: int = 50,
                     ctx: dict = Depends(require_workspace)):
    return await _list_kind("call", ctx, customer_id, deal_id, page, limit)


@router.post("/calls")
async def log_call(body: CallLogIn, ctx: dict = Depends(require_workspace)):
    await ensure_customer_in_workspace(body.customer_id, ctx["workspace_id"])
    await ensure_deal_in_workspace(body.deal_id, ctx["workspace_id"])
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "kind": "call",
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.interactions.insert_one(doc)
    entity_type = "customer" if body.customer_id else ("deal" if body.deal_id else "workspace")
    entity_id = body.customer_id or body.deal_id or ctx["workspace_id"]
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "logged_call",
                       entity_type, entity_id, {"outcome": body.outcome, "duration_seconds": body.duration_seconds})
    doc.pop("_id", None)
    return doc


# ----------- MEETINGS -----------
@router.get("/meetings")
async def list_meetings(customer_id: Optional[str] = None, deal_id: Optional[str] = None,
                        upcoming: bool = False, page: int = 1, limit: int = 50,
                        ctx: dict = Depends(require_workspace)):
    limit = clamp_limit(limit, default=50, maximum=100)
    skip = clamp_skip(page, limit)
    q = workspace_query(ctx, {"kind": "meeting"})
    if customer_id:
        q["customer_id"] = customer_id
    if deal_id:
        q["deal_id"] = deal_id
    if upcoming:
        q["scheduled_at"] = {"$gte": now_iso()}
        q["status"] = {"$ne": "cancelled"}
    return await db.interactions.find(q, {"_id": 0}).sort("scheduled_at", 1 if upcoming else -1).skip(skip).limit(limit).to_list(limit)


@router.post("/meetings")
async def create_meeting(body: MeetingIn, ctx: dict = Depends(require_workspace)):
    await ensure_customer_in_workspace(body.customer_id, ctx["workspace_id"])
    await ensure_deal_in_workspace(body.deal_id, ctx["workspace_id"])
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "kind": "meeting",
        "status": "scheduled",
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **body.model_dump(),
    }
    await db.interactions.insert_one(doc)
    entity_type = "customer" if body.customer_id else ("deal" if body.deal_id else "workspace")
    entity_id = body.customer_id or body.deal_id or ctx["workspace_id"]
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "scheduled_meeting",
                       entity_type, entity_id, {"title": body.title, "scheduled_at": body.scheduled_at})
    doc.pop("_id", None)
    return doc


@router.patch("/meetings/{mid}/status")
async def update_meeting_status(mid: str, body: MeetingStatusIn, ctx: dict = Depends(require_workspace)):
    meeting = await db.interactions.find_one(
        workspace_query(ctx, {"id": mid, "kind": "meeting"}), {"_id": 0}
    )
    if not meeting:
        raise HTTPException(404, "Meeting not found")
    await db.interactions.update_one(
        workspace_query(ctx, {"id": mid, "kind": "meeting"}),
        {"$set": {"status": body.status, "updated_at": now_iso()}},
    )
    if body.status == "completed":
        entity_type = "customer" if meeting.get("customer_id") else ("deal" if meeting.get("deal_id") else "workspace")
        entity_id = meeting.get("customer_id") or meeting.get("deal_id") or ctx["workspace_id"]
        await log_activity(ctx["workspace_id"], ctx["user"]["id"], "completed_meeting",
                           entity_type, entity_id, {"title": meeting.get("title")})
    return {"ok": True}


# ----------- FILES -----------
@router.get("/files")
async def list_files(customer_id: Optional[str] = None, deal_id: Optional[str] = None,
                     page: int = 1, limit: int = 50,
                     ctx: dict = Depends(require_workspace)):
    limit = clamp_limit(limit, default=50, maximum=100)
    skip = clamp_skip(page, limit)
    q = workspace_query(ctx, {"kind": "file"})
    if customer_id:
        q["customer_id"] = customer_id
    if deal_id:
        q["deal_id"] = deal_id
    # Do not send back the raw data_url in the list view — clients fetch a single file to download.
    return await db.interactions.find(q, {"_id": 0, "data_url": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)


@router.get("/files/{fid}")
async def get_file(fid: str, ctx: dict = Depends(require_workspace)):
    doc = await db.interactions.find_one(
        workspace_query(ctx, {"id": fid, "kind": "file"}), {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "File not found")
    return doc


@router.post("/files")
async def upload_file(body: FileMetaIn, ctx: dict = Depends(require_workspace)):
    await ensure_customer_in_workspace(body.customer_id, ctx["workspace_id"])
    await ensure_deal_in_workspace(body.deal_id, ctx["workspace_id"])
    if body.size_bytes > MAX_FILE_BYTES:
        raise HTTPException(413, f"File too large. Maximum {MAX_FILE_BYTES // (1024*1024)} MB per upload.")
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "kind": "file",
        "created_by": ctx["user"]["id"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.interactions.insert_one(doc)
    entity_type = "customer" if body.customer_id else ("deal" if body.deal_id else "workspace")
    entity_id = body.customer_id or body.deal_id or ctx["workspace_id"]
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "uploaded_file",
                       entity_type, entity_id,
                       {"filename": body.filename, "size_bytes": body.size_bytes})
    # Never return the base64 payload in the create response either — clients already have it.
    doc.pop("data_url", None)
    doc.pop("_id", None)
    return doc


@router.delete("/files/{fid}")
async def delete_file(fid: str, ctx: dict = Depends(require_perm("customer", "edit"))):
    r = await db.interactions.delete_one(workspace_query(ctx, {"id": fid, "kind": "file"}))
    if not r.deleted_count:
        raise HTTPException(404, "File not found")
    return {"ok": True}
