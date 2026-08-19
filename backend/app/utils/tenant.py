"""Workspace-scoped safety helpers.

Every referenced foreign key (customer_id, deal_id, lead_id, assignee_id, related_id)
in a request MUST be validated against the caller's workspace to prevent cross-tenant
reference attacks. These helpers centralise that.
"""
import re
from typing import Optional

from fastapi import HTTPException

from app.core.database import db


def escape_regex(s: str) -> str:
    """Escape user input before using it in a MongoDB $regex query."""
    return re.escape(s or "")


def workspace_query(ctx: dict, extra: dict = None) -> dict:
    q = {"workspace_id": ctx["workspace_id"]}
    if extra:
        q.update(extra)
    return q


async def ensure_customer_in_workspace(customer_id: Optional[str], workspace_id: str) -> None:
    if not customer_id:
        return
    exists = await db.customers.find_one(
        {"id": customer_id, "workspace_id": workspace_id}, {"_id": 1}
    )
    if not exists:
        raise HTTPException(400, "Referenced customer not found in this workspace")


async def ensure_deal_in_workspace(deal_id: Optional[str], workspace_id: str) -> None:
    if not deal_id:
        return
    exists = await db.deals.find_one(
        {"id": deal_id, "workspace_id": workspace_id}, {"_id": 1}
    )
    if not exists:
        raise HTTPException(400, "Referenced deal not found in this workspace")


async def ensure_lead_in_workspace(lead_id: Optional[str], workspace_id: str) -> None:
    if not lead_id:
        return
    exists = await db.leads.find_one(
        {"id": lead_id, "workspace_id": workspace_id}, {"_id": 1}
    )
    if not exists:
        raise HTTPException(400, "Referenced lead not found in this workspace")


async def ensure_related_in_workspace(related_type: Optional[str], related_id: Optional[str],
                                      workspace_id: str) -> None:
    if not related_type or not related_id:
        return
    coll = {"customer": db.customers, "lead": db.leads, "deal": db.deals}.get(related_type)
    if coll is None:
        raise HTTPException(400, f"Invalid related_type: {related_type}")
    exists = await coll.find_one(
        {"id": related_id, "workspace_id": workspace_id}, {"_id": 1}
    )
    if not exists:
        raise HTTPException(400, "Referenced record not found in this workspace")


async def ensure_assignee_in_workspace(assignee_id: Optional[str], workspace_id: str) -> None:
    if not assignee_id:
        return
    membership = await db.memberships.find_one(
        {"user_id": assignee_id, "workspace_id": workspace_id}, {"_id": 1}
    )
    if not membership:
        raise HTTPException(400, "Assignee is not a member of this workspace")
