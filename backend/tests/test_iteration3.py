"""NexusCRM Iteration 3 backend tests: RBAC 2.0, deal enhancements + risk,
workspace settings/pipeline, analytics, tickets, audit log, copilot, cross-tenant."""
import os
import uuid
import time
from datetime import datetime, timezone, timedelta
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break
API = f"{BASE_URL}/api"

UNIQUE = uuid.uuid4().hex[:8]
OWNER_EMAIL = f"own3_{UNIQUE}@nexustest.com"
OWNER_PW = "testpass123"
PW = "invpass123"

state = {}


def H(token=None, ws=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if ws:
        h["X-Workspace-Id"] = ws
    return h


@pytest.fixture(scope="session")
def sess():
    return requests.Session()


# ---------- Setup: owner + workspace + invitees of every role ----------
def test_00_setup_owner_workspace(sess):
    r = sess.post(f"{API}/auth/signup",
                  json={"email": OWNER_EMAIL, "password": OWNER_PW, "name": "Owner3"},
                  headers=H())
    assert r.status_code == 200, r.text
    state["owner_token"] = r.json()["token"]
    state["owner_id"] = r.json()["user"]["id"]
    r = sess.post(f"{API}/workspaces",
                  json={"name": f"WS3_{UNIQUE}", "industry": "SaaS"},
                  headers=H(state["owner_token"]))
    assert r.status_code == 200
    ws = r.json()
    state["ws_id"] = ws["id"]
    # Verify default pipeline seeded and plan is starter
    assert ws.get("plan") == "starter"
    assert isinstance(ws.get("pipeline_stages"), list) and len(ws["pipeline_stages"]) >= 5


def _create_invitee(sess, role: str):
    email = f"{role}_{UNIQUE}@nexustest.com"
    r = sess.post(f"{API}/workspaces/invite",
                  json={"email": email, "role": role, "send_email": False},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    token = r.json()["invite_link"].split("/invite/")[-1]
    r = sess.post(f"{API}/invites/{token}/accept",
                  json={"password": PW, "name": role.title()},
                  headers=H())
    assert r.status_code == 200, r.text
    d = r.json()
    # get user id
    r2 = sess.post(f"{API}/auth/login", json={"email": email, "password": PW})
    return {"email": email, "token": d["token"], "user_id": r2.json()["user"]["id"]}


def test_01_setup_invitees_all_roles(sess):
    for role in ("admin", "manager", "member", "support", "viewer"):
        state[role] = _create_invitee(sess, role)
    # Sanity: list members
    r = sess.get(f"{API}/workspaces/members",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    members = r.json()
    assert len(members) == 6  # owner + 5


# ---------- RBAC: viewer / support restrictions ----------
def test_10_viewer_cannot_create_customer(sess):
    r = sess.post(f"{API}/customers", json={"name": "TEST_ViewerCust"},
                  headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_11_viewer_cannot_create_deal(sess):
    r = sess.post(f"{API}/deals", json={"title": "TEST_ViewerDeal", "value": 1, "stage": "lead"},
                  headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_12_viewer_can_get_customers_and_deals(sess):
    r = sess.get(f"{API}/customers",
                 headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 200
    r = sess.get(f"{API}/deals",
                 headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 200


def test_13_support_cannot_create_deal(sess):
    r = sess.post(f"{API}/deals", json={"title": "TEST_SupportDeal", "value": 1, "stage": "lead"},
                  headers=H(state["support"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_14_support_can_create_ticket(sess):
    r = sess.post(f"{API}/tickets",
                  json={"subject": "TEST_SupportTicket", "priority": "high",
                        "status": "open"},
                  headers=H(state["support"]["token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    state["support_ticket_id"] = r.json()["id"]
    assert r.json()["number"].startswith("TKT-")


def test_15_support_can_update_ticket(sess):
    r = sess.put(f"{API}/tickets/{state['support_ticket_id']}",
                 json={"subject": "TEST_SupportTicket-Updated",
                       "priority": "high", "status": "in_progress"},
                 headers=H(state["support"]["token"], state["ws_id"]))
    assert r.status_code == 200


# ---------- Workspace member role management ----------
def test_20_owner_can_change_member_role(sess):
    r = sess.patch(
        f"{API}/workspaces/members/{state['member']['user_id']}/role",
        json={"role": "manager"},
        headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    # revert
    sess.patch(f"{API}/workspaces/members/{state['member']['user_id']}/role",
               json={"role": "member"},
               headers=H(state["owner_token"], state["ws_id"]))


def test_21_cannot_change_own_role(sess):
    r = sess.patch(f"{API}/workspaces/members/{state['owner_id']}/role",
                   json={"role": "admin"},
                   headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 403


def test_22_cannot_change_owner_role_by_admin(sess):
    r = sess.patch(f"{API}/workspaces/members/{state['owner_id']}/role",
                   json={"role": "admin"},
                   headers=H(state["admin"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_23_non_admin_cannot_change_role(sess):
    r = sess.patch(
        f"{API}/workspaces/members/{state['member']['user_id']}/role",
        json={"role": "manager"},
        headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 403
    r = sess.patch(
        f"{API}/workspaces/members/{state['member']['user_id']}/role",
        json={"role": "manager"},
        headers=H(state["manager"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_24_owner_cannot_remove_self(sess):
    r = sess.delete(f"{API}/workspaces/members/{state['owner_id']}",
                    headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 403


def test_25_cannot_remove_owner(sess):
    r = sess.delete(f"{API}/workspaces/members/{state['owner_id']}",
                    headers=H(state["admin"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_26_owner_can_remove_member(sess):
    # Create a throwaway viewer2 to remove
    email = f"del_{UNIQUE}@nexustest.com"
    r = sess.post(f"{API}/workspaces/invite",
                  json={"email": email, "role": "viewer", "send_email": False},
                  headers=H(state["owner_token"], state["ws_id"]))
    tok = r.json()["invite_link"].split("/invite/")[-1]
    sess.post(f"{API}/invites/{tok}/accept",
              json={"password": PW, "name": "DelMe"}, headers=H())
    lr = sess.post(f"{API}/auth/login", json={"email": email, "password": PW})
    uid = lr.json()["user"]["id"]
    r = sess.delete(f"{API}/workspaces/members/{uid}",
                    headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200


# ---------- Workspace settings & pipeline stages ----------
def test_30_get_settings_returns_pipeline_stages(sess):
    r = sess.get(f"{API}/workspaces/settings",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d.get("pipeline_stages"), list)
    assert d["pipeline_stages"][0].get("id") == "lead"


def test_31_settings_get_denied_for_viewer(sess):
    r = sess.get(f"{API}/workspaces/settings",
                 headers=H(state["viewer"]["token"], state["ws_id"]))
    # settings.view -> owner/admin/manager
    assert r.status_code == 403


def test_32_update_settings_partial(sess):
    r = sess.put(f"{API}/workspaces/settings",
                 json={"logo_url": "https://cdn.example.com/logo.png",
                       "industry": "FinTech"},
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    r = sess.get(f"{API}/workspaces/settings",
                 headers=H(state["owner_token"], state["ws_id"]))
    d = r.json()
    assert d["logo_url"] == "https://cdn.example.com/logo.png"
    assert d["industry"] == "FinTech"


def test_33_update_settings_pipeline_stages(sess):
    stages = [
        {"id": "lead", "label": "New Lead", "color": "#111", "probability": 5},
        {"id": "qualified", "label": "Qualified", "color": "#0047FF", "probability": 30},
        {"id": "demo", "label": "Demo Booked", "color": "#7c3aed", "probability": 50},
        {"id": "won", "label": "Won", "color": "#10b981", "probability": 100},
        {"id": "lost", "label": "Lost", "color": "#FF3823", "probability": 0},
    ]
    r = sess.put(f"{API}/workspaces/settings",
                 json={"pipeline_stages": stages},
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    r = sess.get(f"{API}/workspaces/settings",
                 headers=H(state["owner_token"], state["ws_id"]))
    d = r.json()
    assert d["pipeline_stages"][0]["label"] == "New Lead"


def test_34_settings_rejects_duplicate_stage_ids(sess):
    stages = [
        {"id": "lead", "label": "A", "probability": 5},
        {"id": "lead", "label": "B", "probability": 5},
    ]
    r = sess.put(f"{API}/workspaces/settings",
                 json={"pipeline_stages": stages},
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 400


def test_35_settings_manage_denied_for_manager(sess):
    r = sess.put(f"{API}/workspaces/settings",
                 json={"industry": "Hacked"},
                 headers=H(state["manager"]["token"], state["ws_id"]))
    assert r.status_code == 403


# ---------- Deal enhancements + risk detection ----------
def test_40_create_deal_new_fields(sess):
    r = sess.post(f"{API}/deals",
                  json={"title": "TEST_EnhancedDeal", "value": 5000,
                        "stage": "qualified",
                        "probability": 55, "priority": "high",
                        "tags": ["strategic", "q1"],
                        "description": "Big customer",
                        "assignee_id": state["member"]["user_id"],
                        "close_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["probability"] == 55
    assert d["priority"] == "high"
    assert d["tags"] == ["strategic", "q1"]
    assert d["description"] == "Big customer"
    state["deal_id"] = d["id"]


def test_41_get_deals_includes_risk(sess):
    r = sess.get(f"{API}/deals",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    for d in r.json():
        assert "risk" in d
        assert "level" in d["risk"]
        assert "reasons" in d["risk"]


def test_42_risk_medium_or_high_after_stale(sess):
    # Insert a deal directly with an old updated_at via API create + manipulate
    # We cannot manipulate updated_at via API. Instead, set close_date in the past
    # to trigger overdue reason (guarantees at least 1 reason).
    r = sess.post(f"{API}/deals",
                  json={"title": "TEST_OverdueDeal", "value": 1000,
                        "stage": "proposal", "probability": 10,
                        "close_date": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    did = r.json()["id"]
    r = sess.get(f"{API}/deals", headers=H(state["owner_token"], state["ws_id"]))
    target = next((x for x in r.json() if x["id"] == did), None)
    assert target and target["risk"]["level"] in ("medium", "high")
    assert any("verdue" in reason.lower() for reason in target["risk"]["reasons"])


# ---------- Analytics ----------
def test_50_analytics_overview_shape(sess):
    r = sess.get(f"{API}/analytics/overview",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("totals", "forecast", "kpis", "pipeline_by_stage",
              "leads_by_status", "at_risk_deals"):
        assert k in d, f"Missing {k}"
    for k in ("customers", "leads", "deals", "open_tasks",
              "open_tickets", "pipeline_value", "won_value"):
        assert k in d["totals"], f"totals missing {k}"
    for k in ("committed", "best_case", "pipeline", "weighted", "forecast"):
        assert k in d["forecast"]
    for k in ("win_rate", "avg_deal_size", "sales_cycle_days",
              "won_count", "lost_count"):
        assert k in d["kpis"]
    # pipeline_by_stage entries should have label & color
    for s in d["pipeline_by_stage"]:
        assert "label" in s and "color" in s and "stage" in s


# ---------- Tickets ----------
def test_60_create_ticket_auto_number(sess):
    # Reset ticket numbering: count existing
    r = sess.post(f"{API}/tickets",
                  json={"subject": "TEST_Ticket1", "priority": "medium",
                        "status": "open"},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    n1 = r.json()["number"]
    assert n1.startswith("TKT-") and len(n1) == 9
    r = sess.post(f"{API}/tickets",
                  json={"subject": "TEST_Ticket2", "priority": "high",
                        "status": "open"},
                  headers=H(state["owner_token"], state["ws_id"]))
    n2 = r.json()["number"]
    state["ticket_id"] = r.json()["id"]
    assert int(n2.split("-")[1]) == int(n1.split("-")[1]) + 1


def test_61_list_tickets(sess):
    r = sess.get(f"{API}/tickets",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 2


def test_62_update_ticket(sess):
    r = sess.put(f"{API}/tickets/{state['ticket_id']}",
                 json={"subject": "TEST_Ticket2-Upd", "priority": "urgent",
                       "status": "in_progress"},
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    r = sess.get(f"{API}/tickets/{state['ticket_id']}",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.json()["priority"] == "urgent"


def test_63_ticket_stats_overview(sess):
    r = sess.get(f"{API}/tickets/stats/overview",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    d = r.json()
    for k in ("open", "resolved", "high_priority", "total"):
        assert k in d


def test_64_delete_ticket_admin_only(sess):
    # member (default role) cannot delete
    r = sess.delete(f"{API}/tickets/{state['ticket_id']}",
                    headers=H(state["member"]["token"], state["ws_id"]))
    assert r.status_code == 403
    # owner can
    r = sess.delete(f"{API}/tickets/{state['ticket_id']}",
                    headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200


# ---------- Audit log ----------
def test_70_audit_log_admin_only(sess):
    r = sess.get(f"{API}/audit-logs",
                 headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 403
    r = sess.get(f"{API}/audit-logs",
                 headers=H(state["member"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_71_audit_log_records_actions(sess):
    r = sess.get(f"{API}/audit-logs",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    logs = r.json()
    actions = {(l["action"], l["resource"]) for l in logs}
    # from earlier tests we updated settings, changed role, created tickets, etc.
    assert ("updated", "workspace") in actions
    assert ("role_changed", "member") in actions
    assert any(l["resource"] == "ticket" for l in logs)


# ---------- Copilot ----------
def test_80_copilot_returns_answer(sess):
    r = sess.post(f"{API}/ai/copilot",
                  json={"message": "Which deals are at risk?"},
                  headers=H(state["owner_token"], state["ws_id"]))
    # AI may be slow — allow 30s
    assert r.status_code == 200, r.text
    d = r.json()
    assert "answer" in d
    assert isinstance(d["answer"], str) and len(d["answer"]) > 5


def test_81_copilot_denied_for_viewer(sess):
    r = sess.post(f"{API}/ai/copilot",
                  json={"message": "hello"},
                  headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 403


# ---------- AI lead score enhanced ----------
def test_90_ai_score_lead(sess):
    # create a lead first
    r = sess.post(f"{API}/leads",
                  json={"name": "TEST_ScoreMe", "company": "BigCo",
                        "email": "sm@bigco.com", "source": "web",
                        "status": "qualified", "value": 25000},
                  headers=H(state["owner_token"], state["ws_id"]))
    lid = r.json()["id"]
    r = sess.post(f"{API}/ai/score-lead/{lid}",
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert "score" in d and isinstance(d["score"], int)
    assert d["classification"] in ("hot", "warm", "cold")
    assert isinstance(d["reasons"], list)
    # persistence
    r2 = sess.get(f"{API}/leads",
                  headers=H(state["owner_token"], state["ws_id"]))
    lead = next(x for x in r2.json() if x["id"] == lid)
    assert lead.get("score") == d["score"]
    assert lead.get("classification") == d["classification"]


# ---------- Cross-tenant isolation ----------
def test_99_cross_tenant_blocked(sess):
    # Create a second workspace with a different user (owner_B)
    email_b = f"ownB_{UNIQUE}@nexustest.com"
    r = sess.post(f"{API}/auth/signup",
                  json={"email": email_b, "password": PW, "name": "OwnerB"})
    tok_b = r.json()["token"]
    r = sess.post(f"{API}/workspaces", json={"name": f"WSB_{UNIQUE}"},
                  headers=H(tok_b))
    wsb = r.json()["id"]
    # Now, owner A tries to access ws B => 403
    r = sess.get(f"{API}/customers",
                 headers=H(state["owner_token"], wsb))
    assert r.status_code == 403
