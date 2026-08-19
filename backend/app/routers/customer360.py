"""Customer 360 aggregate views: header summary + unified timeline."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.permissions import require_perm
from app.utils.pagination import clamp_limit
from app.utils.tenant import workspace_query

router = APIRouter()


@router.get("/customers/{cid}/summary")
async def customer_360_summary(cid: str, ctx: dict = Depends(require_perm("customer", "view"))):
    customer = await db.customers.find_one(workspace_query(ctx, {"id": cid}), {"_id": 0})
    if not customer:
        raise HTTPException(404, "Not found")

    deals = await db.deals.find(workspace_query(ctx, {"customer_id": cid}), {"_id": 0}).to_list(200)
    open_deals = [d for d in deals if d.get("stage") not in ("won", "lost")]
    total_value = sum(d.get("value") or 0 for d in deals)
    open_value = sum(d.get("value") or 0 for d in open_deals)

    tasks = await db.tasks.find(
        workspace_query(ctx, {"related_type": "customer", "related_id": cid}), {"_id": 0}
    ).to_list(200)
    open_tasks = [t for t in tasks if t.get("status") != "done"]

    tickets = await db.tickets.find(workspace_query(ctx, {"customer_id": cid}), {"_id": 0}).to_list(100)
    open_tickets = [t for t in tickets if t.get("status") not in ("resolved", "closed")]

    # Owner is the user who owns the most-valuable open deal, else the creator, else None.
    owner_id = customer.get("owner_id")
    if not owner_id and open_deals:
        owner_id = max(open_deals, key=lambda d: d.get("value") or 0).get("assignee_id")
    if not owner_id:
        owner_id = customer.get("created_by")
    owner = None
    if owner_id:
        u = await db.users.find_one({"id": owner_id}, {"_id": 0, "password": 0})
        if u:
            owner = {"id": u["id"], "name": u.get("name"), "email": u.get("email")}

    # Best lead score for a matching lead (same email or same name)
    lead_score = None
    match_leads = []
    if customer.get("email"):
        match_leads = await db.leads.find(
            workspace_query(ctx, {"email": customer["email"]}), {"_id": 0}
        ).to_list(10)
    if not match_leads:
        match_leads = await db.leads.find(
            workspace_query(ctx, {"name": customer["name"]}), {"_id": 0}
        ).to_list(10)
    scored = [l.get("score") for l in match_leads if l.get("score") is not None]
    if scored:
        lead_score = max(scored)

    # Last + next activity
    last_activity = await db.activities.find_one(
        workspace_query(ctx, {"entity_id": cid}),
        {"_id": 0}, sort=[("created_at", -1)]
    )
    next_meeting = await db.interactions.find_one(
        workspace_query(ctx, {"kind": "meeting", "customer_id": cid,
                              "status": {"$ne": "cancelled"}}),
        {"_id": 0, "data_url": 0}, sort=[("scheduled_at", 1)]
    )

    return {
        "customer": customer,
        "owner": owner,
        "totals": {
            "deals": len(deals),
            "open_deals": len(open_deals),
            "total_value": total_value,
            "open_value": open_value,
            "open_tasks": len(open_tasks),
            "open_tickets": len(open_tickets),
            "tickets": len(tickets),
        },
        "lead_score": lead_score,
        "last_activity": last_activity,
        "next_meeting": next_meeting,
    }


@router.get("/customers/{cid}/timeline")
async def customer_timeline(cid: str, limit: int = 100,
                            ctx: dict = Depends(require_perm("customer", "view"))):
    """Merge activities + notes + interactions into a single chronological feed."""
    limit = clamp_limit(limit, default=100, maximum=200)
    wid = ctx["workspace_id"]

    # Base activity rows (created/updated/stage_changed/etc.)
    # Filter out actions that are already represented by the interactions feed to avoid dupes.
    _INTERACTION_ACTIONS = {
        "sent_email", "received_email", "logged_call",
        "scheduled_meeting", "completed_meeting", "uploaded_file",
    }
    acts = await db.activities.find(
        {"workspace_id": wid, "entity_id": cid,
         "action": {"$nin": list(_INTERACTION_ACTIONS)}}, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)

    # Notes → author name
    notes = await db.notes.find(
        {"workspace_id": wid, "related_type": "customer", "related_id": cid}, {"_id": 0}
    ).sort("created_at", -1).to_list(limit)

    # Interactions (emails/calls/meetings/files)
    interactions = await db.interactions.find(
        {"workspace_id": wid, "customer_id": cid}, {"_id": 0, "data_url": 0}
    ).sort("created_at", -1).to_list(limit)

    # Deal stage changes & creations tagged to this customer via deal.customer_id
    deals = await db.deals.find(
        {"workspace_id": wid, "customer_id": cid}, {"_id": 0}
    ).to_list(200)
    deal_ids = {d["id"] for d in deals}
    deal_acts = await db.activities.find(
        {"workspace_id": wid, "entity_type": "deal", "entity_id": {"$in": list(deal_ids)}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(limit) if deal_ids else []

    # Author/actor names in one query
    actor_ids = {a.get("actor_id") for a in (acts + deal_acts) if a.get("actor_id")}
    actor_ids |= {n.get("author_id") for n in notes if n.get("author_id")}
    actor_ids |= {i.get("created_by") for i in interactions if i.get("created_by")}
    actor_ids.discard(None)
    users = await db.users.find({"id": {"$in": list(actor_ids)}}, {"_id": 0, "password": 0}).to_list(200)
    umap = {u["id"]: {"id": u["id"], "name": u.get("name"), "email": u.get("email")} for u in users}

    events = []
    for a in acts:
        events.append({
            "id": a["id"], "kind": "activity", "type": a.get("action"),
            "entity_type": a.get("entity_type"), "entity_id": a.get("entity_id"),
            "actor": umap.get(a.get("actor_id"), {"name": "System"}),
            "meta": a.get("meta") or {}, "created_at": a["created_at"],
            "description": _describe_activity(a),
        })
    for a in deal_acts:
        events.append({
            "id": a["id"], "kind": "activity", "type": a.get("action"),
            "entity_type": "deal", "entity_id": a.get("entity_id"),
            "actor": umap.get(a.get("actor_id"), {"name": "System"}),
            "meta": a.get("meta") or {}, "created_at": a["created_at"],
            "description": _describe_activity(a),
        })
    for n in notes:
        events.append({
            "id": n["id"], "kind": "note", "type": "note_added",
            "actor": umap.get(n.get("author_id"), {"name": "Unknown"}),
            "created_at": n["created_at"],
            "description": n.get("content", ""),
        })
    for i in interactions:
        events.append({
            "id": i["id"], "kind": i.get("kind"),
            "type": _interaction_type(i),
            "actor": umap.get(i.get("created_by"), {"name": "System"}),
            "created_at": i["created_at"],
            "description": _describe_interaction(i),
            "meta": {k: i.get(k) for k in ("subject", "title", "direction", "outcome",
                                            "duration_seconds", "scheduled_at",
                                            "filename", "size_bytes", "status") if k in i},
            "entity_type": "customer",
            "entity_id": cid,
        })

    events.sort(key=lambda e: e["created_at"], reverse=True)
    return events[:limit]


def _interaction_type(i: dict) -> str:
    k = i.get("kind")
    if k == "email":
        return "email_sent" if i.get("direction") == "outbound" else "email_received"
    if k == "meeting":
        return "meeting_scheduled" if i.get("status") != "completed" else "meeting_completed"
    if k == "call":
        return "call_logged"
    if k == "file":
        return "file_uploaded"
    return k or "interaction"


def _describe_interaction(i: dict) -> str:
    k = i.get("kind")
    if k == "email":
        arrow = "→" if i.get("direction") == "outbound" else "←"
        peer = i.get("to_email") if i.get("direction") == "outbound" else i.get("from_email")
        return f"{arrow} {peer or ''} · {i.get('subject','(no subject)')}".strip(" ·")
    if k == "call":
        secs = i.get("duration_seconds") or 0
        mm = secs // 60
        return f"Call · {i.get('outcome','')} · {mm}m — {i.get('summary','')}".strip(" —")
    if k == "meeting":
        return f"{i.get('title','')} @ {i.get('scheduled_at','')}"
    if k == "file":
        kb = round((i.get("size_bytes") or 0) / 1024)
        return f"{i.get('filename','')} ({kb} KB)"
    return ""


def _describe_activity(a: dict) -> str:
    verb = a.get("action", "").replace("_", " ")
    ent = a.get("entity_type", "")
    meta = a.get("meta") or {}
    label = meta.get("title") or meta.get("name") or meta.get("subject") or ""
    stage = meta.get("stage")
    if stage:
        return f"{verb} {ent} → {stage} {label}".strip()
    return f"{verb} {ent} {label}".strip()
