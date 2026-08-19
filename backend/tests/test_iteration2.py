"""NexusCRM Iteration 2 backend tests: invites, notifications, search, billing."""
import os
import uuid
import time
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
OWNER_EMAIL = f"own_{UNIQUE}@nexustest.com"
OWNER_PW = "testpass123"
INVITEE_EMAIL = f"inv_{UNIQUE}@nexustest.com"

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


# --- Setup: owner + workspace ---
def test_00_setup_owner_and_ws(sess):
    r = sess.post(f"{API}/auth/signup", json={
        "email": OWNER_EMAIL, "password": OWNER_PW, "name": "Owner"
    }, headers=H())
    assert r.status_code == 200, r.text
    state["owner_token"] = r.json()["token"]
    state["owner_id"] = r.json()["user"]["id"]

    r = sess.post(f"{API}/workspaces", json={"name": f"WS_{UNIQUE}"}, headers=H(state["owner_token"]))
    assert r.status_code == 200
    state["ws_id"] = r.json()["id"]


# ---------- Invites ----------
def test_10_invite_generates_link_no_email(sess):
    r = sess.post(f"{API}/workspaces/invite",
                  json={"email": INVITEE_EMAIL, "role": "member", "send_email": False},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert "/invite/" in d["invite_link"]
    assert d["email_sent"] is False
    # Extract token
    state["invite_token"] = d["invite_link"].split("/invite/")[-1]


def test_11_invite_send_email_true(sess):
    r = sess.post(f"{API}/workspaces/invite",
                  json={"email": f"other_{UNIQUE}@nexustest.com", "role": "member", "send_email": True},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert "invite_link" in d
    # email_sent may be True or False (provider), both acceptable
    assert isinstance(d["email_sent"], bool)


def test_12_get_invite_valid_token(sess):
    r = sess.get(f"{API}/invites/{state['invite_token']}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["email"] == INVITEE_EMAIL
    assert d["role"] == "member"
    assert d["workspace"]["id"] == state["ws_id"]
    assert "user_exists" in d


def test_13_get_invite_invalid_token(sess):
    r = sess.get(f"{API}/invites/not-a-valid-token")
    assert r.status_code == 400


def test_14_accept_invite_creates_user(sess):
    r = sess.post(f"{API}/invites/{state['invite_token']}/accept",
                  json={"password": "invitedpw123", "name": "Invited User"},
                  headers=H())
    assert r.status_code == 200, r.text
    d = r.json()
    assert "token" in d
    assert d["workspace_id"] == state["ws_id"]
    state["invitee_token"] = d["token"]


def test_15_invitee_can_login(sess):
    r = sess.post(f"{API}/auth/login",
                  json={"email": INVITEE_EMAIL, "password": "invitedpw123"},
                  headers=H())
    assert r.status_code == 200, r.text
    state["invitee_id"] = r.json()["user"]["id"]
    state["invitee_token"] = r.json()["token"]


def test_16_invitee_is_member(sess):
    r = sess.get(f"{API}/workspaces/members", headers=H(state["owner_token"], state["ws_id"]))
    members = r.json()
    assert any(m.get("email") == INVITEE_EMAIL for m in members)


# ---------- Notifications ----------
def test_20_task_assign_creates_notification(sess):
    # Owner assigns task to invitee
    r = sess.post(f"{API}/tasks",
                  json={"title": "TEST_Assigned to invitee", "priority": "high",
                        "status": "todo", "assignee_id": state["invitee_id"]},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    state["task_id"] = r.json()["id"]
    time.sleep(0.5)
    # Invitee should have notification
    r = sess.get(f"{API}/notifications", headers=H(state["invitee_token"], state["ws_id"]))
    assert r.status_code == 200
    d = r.json()
    assert d["unread"] >= 1
    assert any(n["kind"] == "task_assigned" for n in d["items"])
    state["notif_id"] = next(n["id"] for n in d["items"] if n["kind"] == "task_assigned")


def test_21_deal_stage_notifies_others(sess):
    # create customer, deal, then move stage
    c = sess.post(f"{API}/customers", json={"name": "TEST_C"},
                  headers=H(state["owner_token"], state["ws_id"])).json()
    d = sess.post(f"{API}/deals",
                  json={"title": "TEST_D", "value": 1000, "stage": "lead",
                        "customer_id": c["id"]},
                  headers=H(state["owner_token"], state["ws_id"])).json()
    r = sess.patch(f"{API}/deals/{d['id']}/stage", json={"stage": "proposal"},
                   headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    time.sleep(0.5)
    r = sess.get(f"{API}/notifications", headers=H(state["invitee_token"], state["ws_id"]))
    items = r.json()["items"]
    assert any(n["kind"] == "deal_stage" for n in items)


def test_22_mark_single_read(sess):
    r = sess.post(f"{API}/notifications/{state['notif_id']}/read",
                  headers=H(state["invitee_token"], state["ws_id"]))
    assert r.status_code == 200
    r = sess.get(f"{API}/notifications", headers=H(state["invitee_token"], state["ws_id"]))
    items = r.json()["items"]
    marked = next(n for n in items if n["id"] == state["notif_id"])
    assert marked["read"] is True


def test_23_mark_all_read(sess):
    r = sess.post(f"{API}/notifications/read-all",
                  headers=H(state["invitee_token"], state["ws_id"]))
    assert r.status_code == 200
    r = sess.get(f"{API}/notifications", headers=H(state["invitee_token"], state["ws_id"]))
    assert r.json()["unread"] == 0


# ---------- Global Search ----------
def test_30_search_scoped(sess):
    # Create a customer/lead/deal
    sess.post(f"{API}/customers", json={"name": "TEST_SearchAcme", "company": "Acme"},
              headers=H(state["owner_token"], state["ws_id"]))
    sess.post(f"{API}/leads", json={"name": "TEST_SearchLeadJane"},
              headers=H(state["owner_token"], state["ws_id"]))
    sess.post(f"{API}/deals", json={"title": "TEST_SearchDealMega", "value": 1, "stage": "lead"},
              headers=H(state["owner_token"], state["ws_id"]))
    r = sess.get(f"{API}/search?q=Search",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert any("SearchAcme" in c["name"] for c in d["customers"])
    assert any("SearchLeadJane" in l["name"] for l in d["leads"])
    assert any("SearchDealMega" in x["title"] for x in d["deals"])
    assert len(d["customers"]) <= 6 and len(d["leads"]) <= 6 and len(d["deals"]) <= 6


def test_31_search_scoped_to_workspace(sess):
    # Create another workspace, search should not return other workspace's items
    r = sess.post(f"{API}/workspaces", json={"name": f"OtherWS_{UNIQUE}"},
                  headers=H(state["owner_token"]))
    other_ws = r.json()["id"]
    r = sess.get(f"{API}/search?q=Search", headers=H(state["owner_token"], other_ws))
    assert r.status_code == 200
    d = r.json()
    assert d["customers"] == [] and d["leads"] == [] and d["deals"] == []


# ---------- Billing ----------
def test_40_billing_plans(sess):
    r = sess.get(f"{API}/billing/plans")
    assert r.status_code == 200
    plans = r.json()["plans"]
    assert plans["starter"]["price"] == 0
    assert plans["pro"]["price"] == 29
    assert plans["team"]["price"] == 79


def test_41_billing_subscription_defaults_starter(sess):
    r = sess.get(f"{API}/billing/subscription",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    # Default plan should be starter or free (workspace was created before Iter2)
    assert d["plan"] in ("starter", "free")


def test_42_checkout_pro_returns_stripe_url(sess):
    r = sess.post(f"{API}/billing/checkout",
                  json={"plan_id": "pro", "origin_url": BASE_URL},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["checkout_url"].startswith("https://checkout.stripe.com")
    assert d["session_id"]
    state["session_id"] = d["session_id"]


def test_43_checkout_rejects_starter(sess):
    r = sess.post(f"{API}/billing/checkout",
                  json={"plan_id": "starter", "origin_url": BASE_URL},
                  headers=H(state["owner_token"], state["ws_id"]))
    # Pydantic Literal validation → 422, or manual 400
    assert r.status_code in (400, 422)


def test_44_checkout_rejects_free_plan(sess):
    r = sess.post(f"{API}/billing/checkout",
                  json={"plan_id": "free", "origin_url": BASE_URL},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code in (400, 422)


def test_45_payments_status(sess):
    r = sess.get(f"{API}/payments/status/{state['session_id']}",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    d = r.json()
    assert d["session_id"] == state["session_id"]
    assert d["payment_status"] in ("pending", "paid", "initiated")


def test_46_payments_status_unknown_session(sess):
    r = sess.get(f"{API}/payments/status/nonexistent-session-id",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 404


def test_47_payments_status_requires_auth(sess):
    r = sess.get(f"{API}/payments/status/{state['session_id']}")
    assert r.status_code in (401, 422)
