"""Dashboard analytics aggregate."""
from datetime import datetime

from fastapi import APIRouter, Depends

from app.core.database import db
from app.dependencies.tenant import require_workspace
from app.services.deal_service import DEFAULT_PIPELINE_STAGES, compute_deal_risk

router = APIRouter()


@router.get("/analytics/overview")
async def analytics_overview(ctx: dict = Depends(require_workspace)):
    wid = ctx["workspace_id"]
    total_customers = await db.customers.count_documents({"workspace_id": wid})
    total_leads = await db.leads.count_documents({"workspace_id": wid})
    total_deals = await db.deals.count_documents({"workspace_id": wid})
    open_tasks = await db.tasks.count_documents({"workspace_id": wid, "status": {"$ne": "done"}})
    open_tickets = await db.tickets.count_documents({"workspace_id": wid, "status": {"$nin": ["resolved", "closed"]}})

    workspace = await db.workspaces.find_one({"id": wid}, {"_id": 0})
    stages = workspace.get("pipeline_stages") or DEFAULT_PIPELINE_STAGES
    stage_prob = {s["id"]: s.get("probability", 50) for s in stages}

    pipeline = await db.deals.aggregate([
        {"$match": {"workspace_id": wid}},
        {"$group": {"_id": "$stage", "value": {"$sum": "$value"}, "count": {"$sum": 1}}},
    ]).to_list(50)
    stage_map = {p["_id"]: p for p in pipeline}
    by_stage = [
        {
            "stage": s["id"],
            "label": s["label"],
            "color": s.get("color", "#0047FF"),
            "value": stage_map.get(s["id"], {}).get("value", 0),
            "count": stage_map.get(s["id"], {}).get("count", 0),
        }
        for s in stages
    ]

    leads_agg = await db.leads.aggregate([
        {"$match": {"workspace_id": wid}},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]).to_list(20)
    leads_by_status = [{"status": p["_id"], "count": p["count"]} for p in leads_agg]

    won_value = stage_map.get("won", {}).get("value", 0)
    won_count = stage_map.get("won", {}).get("count", 0)
    lost_count = stage_map.get("lost", {}).get("count", 0)
    total_closed = won_count + lost_count
    win_rate = round((won_count / total_closed) * 100, 1) if total_closed else 0.0
    avg_deal_size = round(won_value / won_count, 2) if won_count else 0.0

    open_deals = await db.deals.find(
        {"workspace_id": wid, "stage": {"$nin": ["won", "lost"]}}, {"_id": 0}
    ).to_list(1000)
    weighted = 0.0
    committed = 0.0
    best_case = 0.0
    for d in open_deals:
        prob = d.get("probability") if d.get("probability") is not None else stage_prob.get(d.get("stage"), 50)
        v = float(d.get("value") or 0)
        weighted += v * (prob / 100.0)
        if prob >= 90:
            committed += v
        if prob >= 60:
            best_case += v
    total_pipeline = sum(d.get("value") or 0 for d in open_deals)
    forecast = weighted + won_value

    won_deals = await db.deals.find({"workspace_id": wid, "stage": "won"}, {"_id": 0}).to_list(500)
    cycle_days = 0.0
    if won_deals:
        total_days = 0
        n = 0
        for d in won_deals:
            try:
                c = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
                u = datetime.fromisoformat(d["updated_at"].replace("Z", "+00:00"))
                total_days += (u - c).days
                n += 1
            except Exception:
                pass
        cycle_days = round(total_days / n, 1) if n else 0.0

    at_risk = []
    for d in open_deals:
        r = compute_deal_risk(d)
        if r["level"] in ("medium", "high"):
            at_risk.append({**d, "risk": r})
    at_risk.sort(key=lambda x: (x["risk"]["level"] == "high", x.get("value") or 0), reverse=True)

    return {
        "totals": {
            "customers": total_customers,
            "leads": total_leads,
            "deals": total_deals,
            "open_tasks": open_tasks,
            "open_tickets": open_tickets,
            "won_value": won_value,
            "pipeline_value": total_pipeline,
        },
        "forecast": {
            "committed": round(committed, 2),
            "best_case": round(best_case, 2),
            "pipeline": round(total_pipeline, 2),
            "weighted": round(weighted, 2),
            "forecast": round(forecast, 2),
        },
        "kpis": {
            "win_rate": win_rate,
            "avg_deal_size": avg_deal_size,
            "sales_cycle_days": cycle_days,
            "won_count": won_count,
            "lost_count": lost_count,
        },
        "pipeline_by_stage": by_stage,
        "leads_by_status": leads_by_status,
        "at_risk_deals": at_risk[:10],
    }
