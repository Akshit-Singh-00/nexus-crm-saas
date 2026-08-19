"""Audit log viewer (admin/owner)."""
from fastapi import APIRouter, Depends

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.utils.pagination import clamp_limit
from app.utils.tenant import workspace_query

router = APIRouter()


@router.get("/audit-logs")
async def list_audit_logs(limit: int = 100, ctx: dict = Depends(require_perm("audit_log", "view"))):
    limit = clamp_limit(limit, default=100, maximum=200)
    return await db.audit_logs.find(workspace_query(ctx), {"_id": 0}).sort("created_at", -1).to_list(limit)
