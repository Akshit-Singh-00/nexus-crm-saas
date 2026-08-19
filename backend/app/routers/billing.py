"""Stripe billing / payments / webhook."""
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import APP_URL, STRIPE_API_KEY
from app.core.database import db
from app.dependencies.permissions import can, require_role
from app.dependencies.tenant import require_workspace
from app.schemas.billing import CheckoutRequestIn
from app.services.billing_service import PLANS, mark_paid
from app.utils.ids import now_iso

stripe.api_key = STRIPE_API_KEY
router = APIRouter()


@router.get("/billing/plans")
async def get_plans():
    return {"plans": PLANS}


@router.get("/billing/subscription")
async def get_subscription(ctx: dict = Depends(require_workspace)):
    workspace = await db.workspaces.find_one({"id": ctx["workspace_id"]}, {"_id": 0})
    plan = workspace.get("plan", "starter")
    if plan == "free":
        plan = "starter"
    return {
        "plan": plan,
        "plan_details": PLANS.get(plan),
        "subscription_id": workspace.get("stripe_subscription_id"),
        "status": workspace.get("subscription_status", "active"),
    }


@router.post("/billing/checkout")
async def billing_checkout(body: CheckoutRequestIn, ctx: dict = Depends(require_role("owner", "admin"))):
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest,
    )
    plan = PLANS.get(body.plan_id)
    if not plan or plan["price"] <= 0:
        raise HTTPException(400, "Invalid plan")

    host = APP_URL or body.origin_url.rstrip("/")
    webhook_url = f"{host}/api/webhook/stripe"
    checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    req = CheckoutSessionRequest(
        amount=float(plan["price"]),
        currency="usd",
        success_url=f"{body.origin_url}/app/billing?status=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{body.origin_url}/app/billing?status=cancel",
        metadata={
            "workspace_id": ctx["workspace_id"],
            "plan_id": body.plan_id,
            "user_id": ctx["user"]["id"],
        },
    )
    session = await checkout.create_checkout_session(req)

    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "workspace_id": ctx["workspace_id"],
        "user_id": ctx["user"]["id"],
        "plan_id": body.plan_id,
        "amount": float(plan["price"]),
        "currency": "usd",
        "status": "initiated",
        "payment_status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    return {"checkout_url": session.url, "session_id": session.session_id}


@router.get("/payments/status/{session_id}")
async def payment_status(session_id: str, ctx: dict = Depends(require_workspace)):
    record = await db.payment_transactions.find_one(
        {"session_id": session_id, "workspace_id": ctx["workspace_id"]}, {"_id": 0}
    )
    if not record:
        raise HTTPException(404, "Transaction not found")
    if record.get("payment_status") != "paid" and can(ctx["role"], "billing", "view"):
        try:
            from emergentintegrations.payments.stripe.checkout import StripeCheckout
            checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{APP_URL}/api/webhook/stripe")
            s = await checkout.get_checkout_status(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                await mark_paid(session_id, record.get("workspace_id"), record.get("plan_id"))
                record = await db.payment_transactions.find_one(
                    {"session_id": session_id, "workspace_id": ctx["workspace_id"]}, {"_id": 0}
                )
        except Exception:
            pass
    return {
        "session_id": record["session_id"],
        "status": record["status"],
        "payment_status": record["payment_status"],
        "plan_id": record.get("plan_id"),
    }


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    from emergentintegrations.payments.stripe.checkout import StripeCheckout
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=f"{APP_URL}/api/webhook/stripe")
    try:
        event = await checkout.handle_webhook(body, sig)
    except Exception as e:
        logging.exception("Webhook verification failed")
        raise HTTPException(400, str(e))

    if event.payment_status == "paid":
        meta = event.metadata or {}
        await mark_paid(event.session_id, meta.get("workspace_id"), meta.get("plan_id"))
    return {"status": "ok"}
