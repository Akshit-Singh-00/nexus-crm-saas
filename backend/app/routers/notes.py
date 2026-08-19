"""Notes CRUD (scoped to a related entity)."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.dependencies.tenant import require_workspace
from app.schemas.tasks import NoteIn
from app.utils.ids import new_id, now_iso
from app.utils.tenant import ensure_related_in_workspace, workspace_query

router = APIRouter()


@router.get("/notes")
async def list_notes(related_type: str, related_id: str, ctx: dict = Depends(require_workspace)):
    if related_type not in ("customer", "lead", "deal"):
        raise HTTPException(400, "Invalid related_type")
    q = workspace_query(ctx, {"related_type": related_type, "related_id": related_id})
    docs = await db.notes.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
    uids = list({d["author_id"] for d in docs})
    users = await db.users.find({"id": {"$in": uids}}, {"_id": 0, "password": 0}).to_list(100)
    umap = {u["id"]: u for u in users}
    for d in docs:
        d["author"] = umap.get(d["author_id"], {"name": "Unknown"})
    return docs


@router.post("/notes")
async def create_note(body: NoteIn, ctx: dict = Depends(require_perm("note", "create"))):
    await ensure_related_in_workspace(body.related_type, body.related_id, ctx["workspace_id"])
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "author_id": ctx["user"]["id"],
        "created_at": now_iso(),
        **body.model_dump(),
    }
    await db.notes.insert_one(doc)
    doc.pop("_id", None)
    return doc
