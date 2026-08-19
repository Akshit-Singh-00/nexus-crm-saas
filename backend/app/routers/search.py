"""Global workspace-scoped search."""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.database import db
from app.core.rate_limit import limiter
from app.dependencies.tenant import require_workspace
from app.utils.tenant import escape_regex

router = APIRouter()


@router.get("/search")
@limiter.limit("120/minute")
async def global_search(request: Request, q: str, ctx: dict = Depends(require_workspace)):
    q = (q or "").strip()
    if len(q) < 2:
        return {"customers": [], "leads": [], "deals": []}
    if len(q) > 100:
        raise HTTPException(400, "Search query too long")
    rx = {"$regex": escape_regex(q), "$options": "i"}
    wq = {"workspace_id": ctx["workspace_id"]}
    customers = await db.customers.find(
        {**wq, "$or": [{"name": rx}, {"email": rx}, {"company": rx}]}, {"_id": 0}
    ).limit(6).to_list(6)
    leads = await db.leads.find(
        {**wq, "$or": [{"name": rx}, {"email": rx}, {"company": rx}]}, {"_id": 0}
    ).limit(6).to_list(6)
    deals = await db.deals.find({**wq, "title": rx}, {"_id": 0}).limit(6).to_list(6)
    return {"customers": customers, "leads": leads, "deals": deals}
