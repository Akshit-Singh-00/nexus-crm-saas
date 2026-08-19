"""NexusCRM comprehensive backend API tests."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # fall back to frontend/.env
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL='):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                break

API = f"{BASE_URL}/api"

UNIQUE = uuid.uuid4().hex[:8]
USER_EMAIL = f"test_{UNIQUE}@nexustest.com"
USER_PW = "testpass123"
USER_NAME = f"Test User {UNIQUE}"

# Shared state across tests
state = {}


@pytest.fixture(scope="session")
def sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def auth_headers(token=None, ws=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if ws:
        h["X-Workspace-Id"] = ws
    return h


# --- Health ---
def test_01_health(sess):
    r = sess.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# --- Auth ---
def test_02_signup(sess):
    r = sess.post(f"{API}/auth/signup", json={
        "email": USER_EMAIL, "password": USER_PW, "name": USER_NAME
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and "user" in data
    assert data["user"]["email"] == USER_EMAIL
    assert "_id" not in data["user"]
    assert "password" not in data["user"]
    state["token"] = data["token"]
    state["user_id"] = data["user"]["id"]


def test_03_signup_duplicate(sess):
    r = sess.post(f"{API}/auth/signup", json={
        "email": USER_EMAIL, "password": USER_PW, "name": USER_NAME
    })
    assert r.status_code == 400


def test_04_login(sess):
    r = sess.post(f"{API}/auth/login", json={
        "email": USER_EMAIL, "password": USER_PW
    })
    assert r.status_code == 200
    assert r.json()["user"]["email"] == USER_EMAIL


def test_05_login_invalid(sess):
    r = sess.post(f"{API}/auth/login", json={
        "email": USER_EMAIL, "password": "wrong"
    })
    assert r.status_code == 401


def test_06_me(sess):
    r = sess.get(f"{API}/auth/me", headers=auth_headers(state["token"]))
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["email"] == USER_EMAIL
    assert "workspaces" in data
    assert isinstance(data["workspaces"], list)


def test_07_me_no_auth(sess):
    r = sess.get(f"{API}/auth/me")
    assert r.status_code == 401


# --- Workspaces ---
def test_10_create_workspace(sess):
    r = sess.post(f"{API}/workspaces",
                  headers=auth_headers(state["token"]),
                  json={"name": f"WS_{UNIQUE}", "industry": "SaaS"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["role"] == "owner"
    assert d["owner_id"] == state["user_id"]
    state["ws_id"] = d["id"]


def test_11_me_has_workspace(sess):
    r = sess.get(f"{API}/auth/me", headers=auth_headers(state["token"]))
    ws = r.json()["workspaces"]
    assert any(w["id"] == state["ws_id"] and w["role"] == "owner" for w in ws)


def test_12_workspace_members(sess):
    r = sess.get(f"{API}/workspaces/members",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    members = r.json()
    assert any(m["id"] == state["user_id"] and m["role"] == "owner" for m in members)


def test_13_workspace_requires_membership(sess):
    # create second user, try to access ws
    other_email = f"other_{UNIQUE}@nexustest.com"
    r = sess.post(f"{API}/auth/signup", json={
        "email": other_email, "password": USER_PW, "name": "Other"
    })
    other_token = r.json()["token"]
    state["other_token"] = other_token
    state["other_email"] = other_email
    r = sess.get(f"{API}/customers", headers=auth_headers(other_token, state["ws_id"]))
    assert r.status_code == 403


# --- Customers ---
def test_20_create_customer(sess):
    r = sess.post(f"{API}/customers",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  json={"name": "TEST_Acme Corp", "email": "acme@test.com",
                        "company": "Acme", "status": "active", "tags": ["vip"]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["name"] == "TEST_Acme Corp"
    assert d["workspace_id"] == state["ws_id"]
    state["cust_id"] = d["id"]


def test_21_list_customers(sess):
    r = sess.get(f"{API}/customers",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    assert any(c["id"] == state["cust_id"] for c in r.json())


def test_22_get_customer(sess):
    r = sess.get(f"{API}/customers/{state['cust_id']}",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    assert r.json()["id"] == state["cust_id"]


def test_23_update_customer(sess):
    r = sess.put(f"{API}/customers/{state['cust_id']}",
                 headers=auth_headers(state["token"], state["ws_id"]),
                 json={"name": "TEST_Acme Updated", "status": "active", "tags": []})
    assert r.status_code == 200
    g = sess.get(f"{API}/customers/{state['cust_id']}",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert g.json()["name"] == "TEST_Acme Updated"


def test_24_customer_search(sess):
    r = sess.get(f"{API}/customers?search=Acme",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    assert any(c["id"] == state["cust_id"] for c in r.json())


def test_25_customer_no_auth(sess):
    r = sess.get(f"{API}/customers")
    assert r.status_code in (401, 422)


# --- Leads ---
def test_30_create_lead(sess):
    r = sess.post(f"{API}/leads",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  json={"name": "TEST_Jane Doe", "email": "jane@big.com",
                        "company": "BigCo", "value": 50000, "status": "new"})
    assert r.status_code == 200, r.text
    state["lead_id"] = r.json()["id"]


def test_31_list_and_search_leads(sess):
    r = sess.get(f"{API}/leads?search=Jane",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    assert any(l["id"] == state["lead_id"] for l in r.json())


def test_32_update_lead(sess):
    r = sess.put(f"{API}/leads/{state['lead_id']}",
                 headers=auth_headers(state["token"], state["ws_id"]),
                 json={"name": "TEST_Jane Doe", "status": "qualified", "value": 60000})
    assert r.status_code == 200


# --- Deals ---
def test_40_create_deal(sess):
    r = sess.post(f"{API}/deals",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  json={"title": "TEST_Big Deal", "value": 100000, "stage": "lead",
                        "customer_id": state["cust_id"]})
    assert r.status_code == 200, r.text
    state["deal_id"] = r.json()["id"]


def test_41_list_deals(sess):
    r = sess.get(f"{API}/deals",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    assert any(d["id"] == state["deal_id"] for d in r.json())


def test_42_update_deal_stage(sess):
    r = sess.patch(f"{API}/deals/{state['deal_id']}/stage",
                   headers=auth_headers(state["token"], state["ws_id"]),
                   json={"stage": "proposal"})
    assert r.status_code == 200
    lst = sess.get(f"{API}/deals",
                   headers=auth_headers(state["token"], state["ws_id"])).json()
    found = next(d for d in lst if d["id"] == state["deal_id"])
    assert found["stage"] == "proposal"


# --- Tasks ---
def test_50_create_task(sess):
    r = sess.post(f"{API}/tasks",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  json={"title": "TEST_Follow up", "priority": "high", "status": "todo"})
    assert r.status_code == 200, r.text
    state["task_id"] = r.json()["id"]


def test_51_update_task(sess):
    r = sess.put(f"{API}/tasks/{state['task_id']}",
                 headers=auth_headers(state["token"], state["ws_id"]),
                 json={"title": "TEST_Follow up", "status": "done", "priority": "high"})
    assert r.status_code == 200


# --- Notes ---
def test_60_create_note(sess):
    r = sess.post(f"{API}/notes",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  json={"content": "TEST_Great meeting today",
                        "related_type": "customer",
                        "related_id": state["cust_id"]})
    assert r.status_code == 200, r.text


def test_61_list_notes_with_author(sess):
    r = sess.get(f"{API}/notes?related_type=customer&related_id={state['cust_id']}",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    notes = r.json()
    assert len(notes) >= 1
    assert "author" in notes[0]
    assert notes[0]["author"].get("email") == USER_EMAIL


# --- Activities ---
def test_70_activities(sess):
    r = sess.get(f"{API}/activities",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    acts = r.json()
    assert len(acts) > 0
    assert "actor" in acts[0]


# --- Analytics ---
def test_80_analytics(sess):
    r = sess.get(f"{API}/analytics/overview",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    d = r.json()
    assert "totals" in d
    assert d["totals"]["customers"] >= 1
    assert d["totals"]["leads"] >= 1
    assert d["totals"]["deals"] >= 1
    assert len(d["pipeline_by_stage"]) == 6
    assert isinstance(d["leads_by_status"], list)


# --- Invite ---
def test_85_invite(sess):
    invite_email = f"invitee_{UNIQUE}@nexustest.com"
    r = sess.post(f"{API}/workspaces/invite",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  json={"email": invite_email, "role": "member"})
    assert r.status_code == 200, r.text
    # verify member listed
    m = sess.get(f"{API}/workspaces/members",
                 headers=auth_headers(state["token"], state["ws_id"])).json()
    assert any(x.get("email") == invite_email for x in m)


# --- RBAC ---
def test_86_viewer_cannot_delete(sess):
    # Invite existing 'other' user as viewer
    r = sess.post(f"{API}/workspaces/invite",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  json={"email": state["other_email"], "role": "viewer"})
    assert r.status_code == 200
    # Now other should be blocked from creating customer (viewer only)
    r = sess.post(f"{API}/customers",
                  headers=auth_headers(state["other_token"], state["ws_id"]),
                  json={"name": "should fail"})
    assert r.status_code == 403


# --- AI (may be slow) ---
def test_90_ai_score_lead(sess):
    r = sess.post(f"{API}/ai/score-lead/{state['lead_id']}",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert 0 <= d["score"] <= 100
    assert isinstance(d["reason"], str) and len(d["reason"]) > 0
    # verify persisted
    lst = sess.get(f"{API}/leads",
                   headers=auth_headers(state["token"], state["ws_id"])).json()
    found = next(l for l in lst if l["id"] == state["lead_id"])
    assert found["score"] == d["score"]


def test_91_ai_summarize_customer(sess):
    r = sess.post(f"{API}/ai/summarize-customer/{state['cust_id']}",
                  headers=auth_headers(state["token"], state["ws_id"]),
                  timeout=60)
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["summary"], str)
    assert len(r.json()["summary"]) > 20


def test_92_ai_sales_forecast(sess):
    r = sess.get(f"{API}/ai/sales-forecast",
                 headers=auth_headers(state["token"], state["ws_id"]),
                 timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "forecast" in d and isinstance(d["forecast"], str)
    assert "pipeline" in d


# --- Cleanup (delete) ---
def test_95_delete_task(sess):
    r = sess.delete(f"{API}/tasks/{state['task_id']}",
                    headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200


def test_96_delete_deal(sess):
    r = sess.delete(f"{API}/deals/{state['deal_id']}",
                    headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200


def test_97_delete_lead(sess):
    r = sess.delete(f"{API}/leads/{state['lead_id']}",
                    headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200


def test_98_delete_customer(sess):
    r = sess.delete(f"{API}/customers/{state['cust_id']}",
                    headers=auth_headers(state["token"], state["ws_id"]))
    assert r.status_code == 200
    g = sess.get(f"{API}/customers/{state['cust_id']}",
                 headers=auth_headers(state["token"], state["ws_id"]))
    assert g.status_code == 404
