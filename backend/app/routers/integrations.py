"""Email + Calendar integration state.

This is the connection-metadata layer only. OAuth secrets and provider tokens
are intentionally NOT handled here — those would live behind a signed callback
in a follow-up. Right now this exposes:

- GET  /integrations                     → list this user's connection statuses
- POST /integrations/connect             → mark a provider as pending/connected
- DELETE /integrations/{provider}        → disconnect

The UI uses this so users can see which providers are wired up and click a
"Connect" button that would kick off OAuth in production.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import db
from app.dependencies.tenant import require_workspace
from app.schemas.interactions import IntegrationConnectIn
from app.utils.ids import new_id, now_iso

router = APIRouter()

PROVIDERS = ("gmail", "outlook", "google_calendar")


@router.get("/integrations")
async def list_integrations(ctx: dict = Depends(require_workspace)):
    docs = await db.integrations.find(
        {"workspace_id": ctx["workspace_id"], "user_id": ctx["user"]["id"]},
        {"_id": 0}
    ).to_list(20)
    by_provider = {d["provider"]: d for d in docs}
    return [
        by_provider.get(p, {
            "provider": p,
            "status": "not_connected",
            "account_email": None,
            "workspace_id": ctx["workspace_id"],
            "user_id": ctx["user"]["id"],
        })
        for p in PROVIDERS
    ]


@router.post("/integrations/connect")
async def connect_integration(body: IntegrationConnectIn, ctx: dict = Depends(require_workspace)):
    if body.provider not in PROVIDERS:
        raise HTTPException(400, "Unknown provider")
    # In production this would return a signed OAuth authorize URL rather than
    # flipping the status directly. For now we mark it 'pending' so the UI can
    # reflect the intent without pretending real emails are flowing.
    doc = {
        "id": new_id(),
        "workspace_id": ctx["workspace_id"],
        "user_id": ctx["user"]["id"],
        "provider": body.provider,
        "status": "pending",
        "account_email": body.account_email,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.integrations.update_one(
        {"workspace_id": ctx["workspace_id"], "user_id": ctx["user"]["id"], "provider": body.provider},
        {"$set": {**doc}},
        upsert=True,
    )
    return {"provider": body.provider, "status": "pending",
            "message": "Provider marked as pending. OAuth handshake would run here in production."}


@router.delete("/integrations/{provider}")
async def disconnect_integration(provider: Literal["gmail", "outlook", "google_calendar"],
                                 ctx: dict = Depends(require_workspace)):
    await db.integrations.delete_one({
        "workspace_id": ctx["workspace_id"],
        "user_id": ctx["user"]["id"],
        "provider": provider,
    })
    return {"ok": True}
