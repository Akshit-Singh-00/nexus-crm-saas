"""Billing plans + payment status helpers."""
from typing import Optional

from app.core.database import db
from app.utils.ids import now_iso

PLANS = {
    "starter": {"name": "Starter", "price": 0.0, "features": ["Up to 100 customers", "Basic AI scoring", "1 workspace"]},
    "pro":     {"name": "Pro",     "price": 29.0, "features": ["Unlimited customers", "AI summaries & forecasts", "Priority support"]},
    "team":    {"name": "Team",    "price": 79.0, "features": ["Everything in Pro", "Advanced RBAC", "Custom AI training", "SLA"]},
}


async def mark_paid(session_id: str, workspace_id: Optional[str], plan_id: Optional[str]) -> None:
    r = await db.payment_transactions.update_one(
        {"session_id": session_id, "payment_status": {"$ne": "paid"}},
        {"$set": {"status": "completed", "payment_status": "paid", "updated_at": now_iso()}},
    )
    if r.modified_count and workspace_id and plan_id:
        await db.workspaces.update_one(
            {"id": workspace_id},
            {"$set": {"plan": plan_id, "subscription_status": "active", "updated_at": now_iso()}},
        )
