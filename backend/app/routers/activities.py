"""Activities feed."""
from fastapi import APIRouter, Depends

from app.core.database import db
from app.dependencies.tenant import require_workspace
from app.utils.pagination import clamp_limit
from app.utils.tenant import workspace_query

router = APIRouter()


@router.get("/activities")
async def list_activities(limit: int = 50, ctx: dict = Depends(require_workspace)):
    limit = clamp_limit(limit, default=50, maximum=100)
    docs = await db.activities.find(
        workspace_query(ctx), {"_id": 0}
    ).sort("created_at", -1).to_list(limit)
    uids = list({d["actor_id"] for d in docs})
    users = await db.users.find({"id": {"$in": uids}}, {"_id": 0, "password": 0}).to_list(100)
    umap = {u["id"]: u for u in users}
    for d in docs:
        d["actor"] = umap.get(d["actor_id"], {"name": "System"})
    return docs
