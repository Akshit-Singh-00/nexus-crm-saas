"""Deal-risk detection + default pipeline stages."""
from datetime import datetime, timezone


DEFAULT_PIPELINE_STAGES = [
    {"id": "lead",        "label": "Lead",        "color": "#94a3b8", "probability": 10},
    {"id": "qualified",   "label": "Qualified",   "color": "#0047FF", "probability": 25},
    {"id": "demo",        "label": "Demo",        "color": "#7c3aed", "probability": 40},
    {"id": "proposal",    "label": "Proposal",    "color": "#0036CC", "probability": 60},
    {"id": "negotiation", "label": "Negotiation", "color": "#0A0A0A", "probability": 80},
    {"id": "won",         "label": "Won",         "color": "#10b981", "probability": 100},
    {"id": "lost",        "label": "Lost",        "color": "#FF3823", "probability": 0},
]


def compute_deal_risk(deal: dict) -> dict:
    if deal.get("stage") in ("won", "lost"):
        return {"level": "none", "reasons": []}
    reasons = []
    now = datetime.now(timezone.utc)
    try:
        updated = datetime.fromisoformat(deal.get("updated_at", "").replace("Z", "+00:00"))
        days_since = (now - updated).days
    except Exception:
        days_since = 0
    if days_since >= 7:
        reasons.append(f"No activity for {days_since} days")
    close_date = deal.get("close_date")
    if close_date:
        try:
            cd = datetime.fromisoformat(close_date)
            if cd.tzinfo is None:
                cd = cd.replace(tzinfo=timezone.utc)
            days_to_close = (cd - now).days
            if days_to_close < 0 and deal.get("stage") not in ("won", "lost"):
                reasons.append(f"Overdue by {-days_to_close} days")
            elif 0 <= days_to_close <= 5 and deal.get("stage") not in ("negotiation", "proposal"):
                reasons.append(f"Close date in {days_to_close} days but not in negotiation")
        except Exception:
            pass
    if deal.get("stage") == "proposal" and days_since >= 5:
        reasons.append("Proposal without follow-up")
    if deal.get("probability", 0) < 20 and days_since >= 3:
        reasons.append("Low probability with stale activity")
    if not reasons:
        return {"level": "none", "reasons": []}
    level = "high" if len(reasons) >= 2 or days_since >= 14 else "medium"
    return {"level": level, "reasons": reasons}
