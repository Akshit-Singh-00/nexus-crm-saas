"""NexusCRM Iteration 4: CSV Import + Workflow Automation tests."""
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
OWNER_EMAIL = f"own4_{UNIQUE}@nexustest.com"
PW = "testpass123"

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


# ----- setup -----
def test_00_setup_owner_ws(sess):
    r = sess.post(f"{API}/auth/signup",
                  json={"email": OWNER_EMAIL, "password": PW, "name": "Owner4"})
    assert r.status_code == 200, r.text
    state["owner_token"] = r.json()["token"]
    state["owner_id"] = r.json()["user"]["id"]
    r = sess.post(f"{API}/workspaces",
                  json={"name": f"WS4_{UNIQUE}", "industry": "SaaS"},
                  headers=H(state["owner_token"]))
    assert r.status_code == 200
    state["ws_id"] = r.json()["id"]


def _invite(sess, role):
    email = f"{role}4_{UNIQUE}@nexustest.com"
    r = sess.post(f"{API}/workspaces/invite",
                  json={"email": email, "role": role, "send_email": False},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    tok = r.json()["invite_link"].split("/invite/")[-1]
    r = sess.post(f"{API}/invites/{tok}/accept",
                  json={"password": PW, "name": role.title()})
    assert r.status_code == 200
    d = r.json()
    r2 = sess.post(f"{API}/auth/login", json={"email": email, "password": PW})
    return {"email": email, "token": d["token"], "user_id": r2.json()["user"]["id"]}


def test_01_setup_roles(sess):
    for role in ("admin", "manager", "member", "viewer"):
        state[role] = _invite(sess, role)


# ---------- CSV Import ----------
LEAD_CSV = (
    "Full Name,Email,Company,Phone,Source,Status,Value\n"
    "Alice Doe,alice@acme.com,Acme,555-1,web,new,1000\n"
    "Bob Roe,bob@bigco.com,BigCo,555-2,referral,qualified,5000\n"
    ",no-name@x.com,X,555-3,web,new,100\n"  # missing name -> error
    "Carol,carol@zeta.com,Zeta,555-4,ads,new,2000\n"
)

CUSTOMER_CSV = (
    "Full Name,Email,Company,Phone,Status\n"
    "Cust1,c1@a.com,ACo,111,active\n"
    "Cust2,c2@b.com,BCo,222,active\n"
)


def test_10_import_preview_lead_shape(sess):
    r = sess.post(f"{API}/import/preview",
                  json={"csv_text": LEAD_CSV, "entity": "lead"},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["headers"] == ["Full Name", "Email", "Company", "Phone", "Source", "Status", "Value"]
    assert len(d["sample_rows"]) <= 5 and len(d["sample_rows"]) >= 1
    assert d["total_rows"] == 4
    assert isinstance(d["target_fields"], list) and "name" in d["target_fields"]
    sm = d["suggested_mapping"]
    # heuristic: Full Name -> name, Email -> email
    assert sm.get("Full Name") == "name", f"Expected 'Full Name' -> 'name', got: {sm}"
    assert sm.get("Email") == "email"


def test_11_import_preview_customer(sess):
    r = sess.post(f"{API}/import/preview",
                  json={"csv_text": CUSTOMER_CSV, "entity": "customer"},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    d = r.json()
    assert d["total_rows"] == 2
    assert d["suggested_mapping"].get("Full Name") == "name"


def test_12_import_preview_viewer_403(sess):
    r = sess.post(f"{API}/import/preview",
                  json={"csv_text": LEAD_CSV, "entity": "lead"},
                  headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_13_import_execute_lead(sess):
    mapping = {"Full Name": "name", "Email": "email", "Company": "company",
               "Phone": "phone", "Source": "source", "Status": "status",
               "Value": "value"}
    r = sess.post(f"{API}/import/execute",
                  json={"csv_text": LEAD_CSV, "entity": "lead", "mapping": mapping},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["inserted"] == 3
    assert d["total"] == 4
    assert len(d["errors"]) == 1 and d["errors"][0]["error"].lower().startswith("missing name")
    # verify persistence
    r2 = sess.get(f"{API}/leads", headers=H(state["owner_token"], state["ws_id"]))
    names = [l["name"] for l in r2.json()]
    assert "Alice Doe" in names and "Bob Roe" in names and "Carol" in names


def test_14_import_execute_viewer_403(sess):
    r = sess.post(f"{API}/import/execute",
                  json={"csv_text": CUSTOMER_CSV, "entity": "customer",
                        "mapping": {"Full Name": "name"}},
                  headers=H(state["viewer"]["token"], state["ws_id"]))
    assert r.status_code == 403


# ---------- Workflow CRUD ----------
def test_20_create_workflow_non_admin_403(sess):
    r = sess.post(f"{API}/workflows",
                  json={"name": "TEST_wf", "trigger": "lead_scored",
                        "conditions": [], "actions": [{"type": "add_tag", "params": {"tag": "x"}}]},
                  headers=H(state["manager"]["token"], state["ws_id"]))
    assert r.status_code == 403
    r = sess.post(f"{API}/workflows",
                  json={"name": "TEST_wf", "trigger": "lead_scored",
                        "conditions": [], "actions": [{"type": "add_tag", "params": {"tag": "x"}}]},
                  headers=H(state["member"]["token"], state["ws_id"]))
    assert r.status_code == 403


def test_21_owner_creates_workflow(sess):
    body = {
        "name": "TEST_HotLeadFollowup",
        "description": "Score>80 add tag+task",
        "trigger": "lead_scored",
        "conditions": [{"field": "score", "op": "gt", "value": 80}],
        "actions": [
            {"type": "create_task", "params": {"title": "TEST_Call hot lead", "priority": "high"}},
            {"type": "add_tag", "params": {"tag": "hot-lead"}},
        ],
        "enabled": True,
    }
    r = sess.post(f"{API}/workflows", json=body,
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["name"] == body["name"]
    assert d["run_count"] == 0
    state["wf_id"] = d["id"]


def test_22_list_workflows(sess):
    r = sess.get(f"{API}/workflows",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    assert any(w["id"] == state["wf_id"] for w in r.json())


def test_23_update_workflow(sess):
    body = {"name": "TEST_HotLeadFollowup2", "trigger": "lead_scored",
            "conditions": [{"field": "score", "op": "gt", "value": 80}],
            "actions": [
                {"type": "create_task", "params": {"title": "TEST_Call hot lead", "priority": "high"}},
                {"type": "add_tag", "params": {"tag": "hot-lead"}},
            ],
            "enabled": True}
    r = sess.put(f"{API}/workflows/{state['wf_id']}", json=body,
                 headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200


# ---------- Workflow execution: lead_scored ----------
def test_30_lead_scored_fires_workflow(sess):
    # create a lead
    r = sess.post(f"{API}/leads",
                  json={"name": "TEST_ScoreTarget", "company": "MegaCorp",
                        "email": "st@mega.com", "source": "web",
                        "status": "qualified", "value": 100000},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    lid = r.json()["id"]
    state["lead_id"] = lid
    # score it (AI call - may take time)
    r = sess.post(f"{API}/ai/score-lead/{lid}",
                  headers=H(state["owner_token"], state["ws_id"]), timeout=60)
    assert r.status_code == 200, r.text
    score = r.json()["score"]
    # allow small time for workflow to complete (fire_workflows awaited inline)
    time.sleep(1)
    # Check workflow run_count
    r = sess.get(f"{API}/workflows",
                 headers=H(state["owner_token"], state["ws_id"]))
    wf = next(w for w in r.json() if w["id"] == state["wf_id"])

    # Check lead now has hot-lead tag (only if condition met)
    r2 = sess.get(f"{API}/leads",
                  headers=H(state["owner_token"], state["ws_id"]))
    lead = next(l for l in r2.json() if l["id"] == lid)
    if score > 80:
        assert wf["run_count"] >= 1, f"run_count should be >=1 when score={score}, got wf={wf}"
        assert "hot-lead" in (lead.get("tags") or []), f"Tag not added. lead={lead}"
        # verify task created
        r3 = sess.get(f"{API}/tasks",
                      headers=H(state["owner_token"], state["ws_id"]))
        tasks = [t for t in r3.json() if t.get("related_id") == lid and t.get("title") == "TEST_Call hot lead"]
        assert len(tasks) >= 1, "workflow-created task not found"
        assert tasks[0]["priority"] == "high"
        state["workflow_fired"] = True
    else:
        # unlikely for a 100k qualified lead; but tolerate
        assert wf["run_count"] == 0
        state["workflow_fired"] = False


# ---------- Workflow condition unreachable ----------
def test_31_unreachable_condition_no_fire(sess):
    # create second workflow with score>200
    body = {
        "name": "TEST_Unreachable",
        "trigger": "lead_scored",
        "conditions": [{"field": "score", "op": "gt", "value": 200}],
        "actions": [{"type": "add_tag", "params": {"tag": "should-not-apply"}}],
        "enabled": True,
    }
    r = sess.post(f"{API}/workflows", json=body,
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    wf2_id = r.json()["id"]
    lid = state["lead_id"]
    r = sess.post(f"{API}/ai/score-lead/{lid}",
                  headers=H(state["owner_token"], state["ws_id"]), timeout=60)
    assert r.status_code == 200
    time.sleep(1)
    r = sess.get(f"{API}/workflows",
                 headers=H(state["owner_token"], state["ws_id"]))
    wf2 = next(w for w in r.json() if w["id"] == wf2_id)
    assert wf2["run_count"] == 0, f"Unreachable workflow should not run, got {wf2}"
    r2 = sess.get(f"{API}/leads",
                  headers=H(state["owner_token"], state["ws_id"]))
    lead = next(l for l in r2.json() if l["id"] == lid)
    assert "should-not-apply" not in (lead.get("tags") or [])


# ---------- Workflow: deal_stage_changed -> notify_user ----------
def test_40_deal_stage_workflow(sess):
    body = {
        "name": "TEST_DealWon",
        "trigger": "deal_stage_changed",
        "conditions": [{"field": "stage", "op": "eq", "value": "won"}],
        "actions": [{"type": "notify_user", "params": {
            "user_id": state["member"]["user_id"],
            "title": "Deal Won!", "body": "Congrats"}}],
        "enabled": True,
    }
    r = sess.post(f"{API}/workflows", json=body,
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    wf_id = r.json()["id"]
    # create a deal assigned to member
    r = sess.post(f"{API}/deals",
                  json={"title": "TEST_WonDeal", "value": 12345,
                        "stage": "qualified", "probability": 60,
                        "assignee_id": state["member"]["user_id"]},
                  headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    # move to won via PATCH stage
    r = sess.patch(f"{API}/deals/{did}/stage",
                   json={"stage": "won"},
                   headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200, r.text
    time.sleep(1)
    # Check workflow run_count
    r = sess.get(f"{API}/workflows",
                 headers=H(state["owner_token"], state["ws_id"]))
    wf = next(w for w in r.json() if w["id"] == wf_id)
    assert wf["run_count"] >= 1
    # Member should get a notification
    r = sess.get(f"{API}/notifications",
                 headers=H(state["member"]["token"], state["ws_id"]))
    assert r.status_code == 200
    notifs = r.json().get("items", [])
    assert any(n.get("title") == "Deal Won!" for n in notifs), \
        f"Notification not created for member. Got: {notifs}"


# ---------- Cross-tenant isolation ----------
def test_50_cross_tenant_no_fire(sess):
    # create a second workspace
    email_b = f"ownB4_{UNIQUE}@nexustest.com"
    r = sess.post(f"{API}/auth/signup",
                  json={"email": email_b, "password": PW, "name": "OwnerB4"})
    tok_b = r.json()["token"]
    r = sess.post(f"{API}/workspaces", json={"name": f"WSB4_{UNIQUE}"},
                  headers=H(tok_b))
    wsb = r.json()["id"]
    # Create workflow in workspace A on lead_created
    body = {"name": "TEST_XT", "trigger": "lead_created",
            "conditions": [],
            "actions": [{"type": "add_tag", "params": {"tag": "from-a"}}],
            "enabled": True}
    r = sess.post(f"{API}/workflows", json=body,
                  headers=H(state["owner_token"], state["ws_id"]))
    wf_id = r.json()["id"]
    # Create a lead in workspace B
    r = sess.post(f"{API}/leads",
                  json={"name": "TEST_XT_Lead", "email": "xt@x.com",
                        "source": "web", "status": "new", "value": 1},
                  headers=H(tok_b, wsb))
    assert r.status_code == 200
    lid_b = r.json()["id"]
    time.sleep(0.5)
    # workspace A workflow run_count should be 0
    r = sess.get(f"{API}/workflows",
                 headers=H(state["owner_token"], state["ws_id"]))
    wf = next(w for w in r.json() if w["id"] == wf_id)
    assert wf["run_count"] == 0, f"Cross-tenant fire! wf={wf}"
    # workspace B lead should not have tag
    r = sess.get(f"{API}/leads", headers=H(tok_b, wsb))
    lead = next(l for l in r.json() if l["id"] == lid_b)
    assert "from-a" not in (lead.get("tags") or [])


# ---------- Workflow delete ----------
def test_60_delete_workflow(sess):
    r = sess.delete(f"{API}/workflows/{state['wf_id']}",
                    headers=H(state["owner_token"], state["ws_id"]))
    assert r.status_code == 200
    r = sess.get(f"{API}/workflows",
                 headers=H(state["owner_token"], state["ws_id"]))
    assert not any(w["id"] == state["wf_id"] for w in r.json())


def test_61_delete_workflow_non_admin_403(sess):
    # create another to test delete perm
    body = {"name": "TEST_DelPerm", "trigger": "lead_created",
            "conditions": [], "actions": [{"type": "add_tag", "params": {"tag": "y"}}],
            "enabled": True}
    r = sess.post(f"{API}/workflows", json=body,
                  headers=H(state["owner_token"], state["ws_id"]))
    wid = r.json()["id"]
    r = sess.delete(f"{API}/workflows/{wid}",
                    headers=H(state["manager"]["token"], state["ws_id"]))
    assert r.status_code == 403
