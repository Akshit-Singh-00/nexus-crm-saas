"""AI endpoints — lead scoring, customer summary, sales forecast, copilot."""
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.database import db
from app.core.rate_limit import limiter
from app.dependencies.permissions import require_perm
from app.schemas.ai import CopilotIn
from app.services.ai_service import call_claude, gather_ai_context
from app.services.audit_service import log_activity
from app.services.workflow_service import fire_workflows
from app.utils.ids import now_iso
from app.utils.tenant import workspace_query

router = APIRouter()


@router.post("/ai/score-lead/{lid}")
@limiter.limit("60/minute")
async def ai_score_lead(request: Request, lid: str, ctx: dict = Depends(require_perm("ai", "use"))):
    lead = await db.leads.find_one(workspace_query(ctx, {"id": lid}), {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    system = ("You are a B2B sales analyst. Score the lead 0-100 for likelihood to convert. "
              "Return STRICT JSON: {\"score\": <int>, \"classification\": \"hot\"|\"warm\"|\"cold\", "
              "\"reasons\": [\"<3-5 short bullet reasons>\"]}. No other text.")
    profile = (
        f"Name: {lead.get('name')}\n"
        f"Email: {lead.get('email')}\n"
        f"Company: {lead.get('company')}\n"
        f"Source: {lead.get('source')}\n"
        f"Status: {lead.get('status')}\n"
        f"Estimated Value: ${lead.get('value', 0)}\n"
    )
    try:
        raw = await call_claude(system, profile)
    except Exception as e:
        logging.exception("AI scoring failed")
        raise HTTPException(500, f"AI error: {e}")
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise HTTPException(500, "AI did not return JSON")
    try:
        data = json.loads(m.group(0))
    except Exception:
        raise HTTPException(500, "AI returned malformed JSON")
    score = int(data.get("score", 0))
    reasons = data.get("reasons") or ([data["reason"]] if data.get("reason") else [])
    classification = data.get("classification") or ("hot" if score >= 75 else "warm" if score >= 50 else "cold")
    await db.leads.update_one(
        workspace_query(ctx, {"id": lid}),
        {"$set": {
            "score": score,
            "score_reason": " · ".join(reasons) if isinstance(reasons, list) else str(reasons),
            "score_reasons": reasons if isinstance(reasons, list) else [str(reasons)],
            "classification": classification,
            "scored_at": now_iso(),
            "updated_at": now_iso(),
        }},
    )
    await log_activity(ctx["workspace_id"], ctx["user"]["id"], "ai_scored", "lead", lid, {"score": score})
    updated_lead = await db.leads.find_one(workspace_query(ctx, {"id": lid}), {"_id": 0})
    if updated_lead:
        await fire_workflows("lead_scored", ctx["workspace_id"], updated_lead)
    return {"score": score, "classification": classification, "reasons": reasons}


@router.post("/ai/summarize-customer/{cid}")
async def ai_summarize_customer(cid: str, ctx: dict = Depends(require_perm("ai", "use"))):
    customer = await db.customers.find_one(workspace_query(ctx, {"id": cid}), {"_id": 0})
    if not customer:
        raise HTTPException(404, "Customer not found")
    notes = await db.notes.find(
        workspace_query(ctx, {"related_type": "customer", "related_id": cid}), {"_id": 0}
    ).to_list(100)
    deals = await db.deals.find(workspace_query(ctx, {"customer_id": cid}), {"_id": 0}).to_list(100)
    system = ("You are a CRM insight engine. Given customer info, notes, and deals, produce a concise "
              "executive summary in 3 short paragraphs: 1) Relationship overview, 2) Opportunity & risks, "
              "3) Recommended next actions. Plain text, no markdown headers.")
    ctx_msg = (
        f"CUSTOMER: {customer.get('name')} | {customer.get('company')} | {customer.get('email')}\n"
        f"Status: {customer.get('status')} | Tags: {', '.join(customer.get('tags', []))}\n\n"
        f"NOTES ({len(notes)}):\n" + "\n".join(f"- {n['content']}" for n in notes[:20]) + "\n\n"
        f"DEALS ({len(deals)}):\n" + "\n".join(f"- {d['title']} | {d['stage']} | ${d['value']}" for d in deals)
    )
    try:
        summary = await call_claude(system, ctx_msg)
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
    return {"summary": summary}


@router.get("/ai/sales-forecast")
async def ai_sales_forecast(ctx: dict = Depends(require_perm("ai", "use"))):
    wid = ctx["workspace_id"]
    pipeline = await db.deals.aggregate([
        {"$match": {"workspace_id": wid}},
        {"$group": {"_id": "$stage", "value": {"$sum": "$value"}, "count": {"$sum": 1}}},
    ]).to_list(20)
    context_str = "Pipeline snapshot:\n" + "\n".join(
        f"- {p['_id']}: {p['count']} deals, ${p['value']:,.0f}" for p in pipeline
    )
    system = ("You are a sales forecasting analyst. Given a pipeline snapshot with deal counts and values per stage, "
              "predict likely revenue for the next quarter and highlight two key risks. Keep it under 120 words, plain text.")
    try:
        forecast = await call_claude(system, context_str)
    except Exception as e:
        raise HTTPException(500, f"AI error: {e}")
    return {"forecast": forecast, "pipeline": pipeline}


@router.post("/ai/copilot")
@limiter.limit("60/minute")
async def ai_copilot(request: Request, body: CopilotIn, ctx: dict = Depends(require_perm("ai", "use"))):
    ctx_snapshot = await gather_ai_context(ctx["workspace_id"], body.context_type, body.context_id)
    system = (
        "You are NexusCRM Sales Copilot — an expert B2B sales analyst embedded in a live CRM. "
        "You are given a snapshot of the user's workspace: deals, leads, tasks, at-risk deals, notes. "
        "Respond concisely and specifically using ONLY the data provided. When suggesting actions, name the actual deal/lead by title. "
        "Format: short bullet points or 1-3 short paragraphs. No markdown headers. When drafting emails, keep them under 150 words and professional. "
        "If the user asks about data that isn't in the snapshot, say what's missing and suggest how to record it."
    )
    prompt = f"USER QUESTION:\n{body.message}\n\nCRM SNAPSHOT:\n{ctx_snapshot}\n"
    try:
        answer = await call_claude(system, prompt)
    except Exception as e:
        raise HTTPException(500, f"Copilot error: {e}")
    return {"answer": answer}
