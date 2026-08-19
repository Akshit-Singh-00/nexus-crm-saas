"""AI service — Claude wrapper + workspace snapshot for the copilot."""
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import EMERGENT_LLM_KEY
from app.core.database import db
from app.services.deal_service import compute_deal_risk, DEFAULT_PIPELINE_STAGES
from app.utils.ids import new_id


async def call_claude(system: str, user_msg: str) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=new_id(),
        system_message=system,
    ).with_model("anthropic", "claude-sonnet-4-6")
    resp = await chat.send_message(UserMessage(text=user_msg))
    return str(resp)


async def gather_ai_context(workspace_id: str, focus_type: Optional[str] = None,
                            focus_id: Optional[str] = None) -> str:
    """Aggregate a compact CRM snapshot for the AI copilot."""
    ws = await db.workspaces.find_one({"id": workspace_id}, {"_id": 0})
    stages = ws.get("pipeline_stages") or DEFAULT_PIPELINE_STAGES
    stage_map = {s["id"]: s.get("probability", 50) for s in stages}

    deals = await db.deals.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)
    open_deals = [d for d in deals if d.get("stage") not in ("won", "lost")]
    won_deals = [d for d in deals if d.get("stage") == "won"]
    at_risk = []
    for d in open_deals:
        r = compute_deal_risk(d)
        if r["level"] in ("medium", "high"):
            at_risk.append({**d, "risk": r})
    at_risk.sort(key=lambda x: (x["risk"]["level"] == "high", x.get("value") or 0), reverse=True)

    leads = await db.leads.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)
    scored = [l for l in leads if l.get("score") is not None]
    top_leads = sorted(scored, key=lambda l: l["score"] or 0, reverse=True)[:5] if scored else leads[:5]

    tasks = await db.tasks.find(
        {"workspace_id": workspace_id, "status": {"$ne": "done"}}, {"_id": 0}
    ).sort("due_date", 1).to_list(10)

    lines = [f"=== WORKSPACE: {ws.get('name')} (industry: {ws.get('industry') or 'n/a'}) ==="]
    lines.append(f"Pipeline stages: {', '.join(s['id'] for s in stages)}")
    lines.append(f"\n[DEALS] total={len(deals)} open={len(open_deals)} won={len(won_deals)}")
    for d in open_deals[:12]:
        prob = d.get("probability") or stage_map.get(d.get("stage"), 50)
        lines.append(f"  - {d.get('title')} | stage={d.get('stage')} | ${d.get('value',0):,.0f} | prob={prob}% | close={d.get('close_date') or '—'}")

    if at_risk:
        lines.append(f"\n[AT-RISK] ({len(at_risk)})")
        for d in at_risk[:6]:
            lines.append(f"  - {d.get('title')} | ${d.get('value',0):,.0f} | risk={d['risk']['level']} | reasons: {'; '.join(d['risk']['reasons'])}")

    lines.append(f"\n[TOP LEADS]")
    for l in top_leads:
        lines.append(f"  - {l.get('name')} ({l.get('company') or '—'}) score={l.get('score','?')} status={l.get('status')} value=${l.get('value',0):,.0f}")

    lines.append(f"\n[OPEN TASKS] ({len(tasks)})")
    for t in tasks[:6]:
        lines.append(f"  - {t.get('title')} | priority={t.get('priority')} | due={t.get('due_date') or '—'}")

    if focus_type and focus_id:
        coll = {"customer": db.customers, "lead": db.leads, "deal": db.deals}.get(focus_type)
        if coll is not None:
            entity = await coll.find_one({"workspace_id": workspace_id, "id": focus_id}, {"_id": 0})
            if entity:
                notes = await db.notes.find(
                    {"workspace_id": workspace_id, "related_type": focus_type, "related_id": focus_id},
                    {"_id": 0}
                ).sort("created_at", -1).to_list(20)
                lines.append(f"\n[FOCUSED {focus_type.upper()}] {entity}")
                if notes:
                    lines.append(f"[NOTES]")
                    for n in notes[:10]:
                        lines.append(f"  - {n['content']}")
    return "\n".join(lines)
