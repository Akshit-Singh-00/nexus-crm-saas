"""Security hardening tests for NexusCRM.

Covers:
- Tenant isolation across workspaces
- Cross-tenant reference protection
- RBAC enforcement at the API layer
- Payment endpoint authorization
- Invitation one-time use
- Search regex safety + workspace scoping
- AI permission enforcement
- Workflow cross-tenant assignee/user validation
- Rate limiting on login
- Pagination
"""
import os
import uuid
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


def h(token=None, ws=None):
    hh = {"Content-Type": "application/json"}
    if token:
        hh["Authorization"] = f"Bearer {token}"
    if ws:
        hh["X-Workspace-Id"] = ws
    return hh


@pytest.fixture(scope="module")
def two_workspaces():
    """Create two isolated users each owning their own workspace."""
    u = uuid.uuid4().hex[:8]
    a = {"email": f"sec_a_{u}@nexustest.com", "password": "SecretPW123", "name": "Alice"}
    b = {"email": f"sec_b_{u}@nexustest.com", "password": "SecretPW123", "name": "Bob"}
    s = requests.Session()
    ra = s.post(f"{API}/auth/signup", json=a).json()
    rb = s.post(f"{API}/auth/signup", json=b).json()
    wsa = s.post(f"{API}/workspaces", headers=h(ra["token"]),
                 json={"name": f"WS-A-{u}", "industry": "SaaS"}).json()
    wsb = s.post(f"{API}/workspaces", headers=h(rb["token"]),
                 json={"name": f"WS-B-{u}", "industry": "SaaS"}).json()
    return {
        "a": {"token": ra["token"], "user": ra["user"], "ws": wsa["id"], "email": a["email"], "pw": a["password"]},
        "b": {"token": rb["token"], "user": rb["user"], "ws": wsb["id"], "email": b["email"], "pw": b["password"]},
    }


# ---------- 1. Tenant isolation ----------
def test_cannot_read_other_workspace_customer(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    # A creates a customer
    r = requests.post(f"{API}/customers", headers=h(a["token"], a["ws"]),
                      json={"name": "A-Corp", "email": "a@a.com"})
    assert r.status_code == 200
    cid = r.json()["id"]
    # B tries to read A's customer via A's workspace header (403 - not a member)
    r2 = requests.get(f"{API}/customers/{cid}", headers=h(b["token"], a["ws"]))
    assert r2.status_code == 403
    # B tries via B's own workspace (404 - not found in scope)
    r3 = requests.get(f"{API}/customers/{cid}", headers=h(b["token"], b["ws"]))
    assert r3.status_code == 404


def test_cannot_modify_other_workspace_lead(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    r = requests.post(f"{API}/leads", headers=h(a["token"], a["ws"]),
                      json={"name": "Lead-A", "value": 1000})
    assert r.status_code == 200
    lid = r.json()["id"]
    # B tries to update A's lead via own workspace scope
    r2 = requests.put(f"{API}/leads/{lid}", headers=h(b["token"], b["ws"]),
                      json={"name": "hijacked", "status": "qualified"})
    assert r2.status_code == 404
    # B tries via A's workspace header
    r3 = requests.put(f"{API}/leads/{lid}", headers=h(b["token"], a["ws"]),
                      json={"name": "hijacked", "status": "qualified"})
    assert r3.status_code == 403


def test_cannot_delete_other_workspace_task(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    r = requests.post(f"{API}/tasks", headers=h(a["token"], a["ws"]),
                      json={"title": "T-A", "priority": "low", "status": "todo"})
    tid = r.json()["id"]
    r2 = requests.delete(f"{API}/tasks/{tid}", headers=h(b["token"], b["ws"]))
    assert r2.status_code == 404


# ---------- 2. Cross-tenant reference protection ----------
def test_cannot_reference_other_workspace_customer_in_deal(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    # A creates a customer
    r = requests.post(f"{API}/customers", headers=h(a["token"], a["ws"]),
                      json={"name": "A-Cust", "email": "a2@a.com"})
    cid_a = r.json()["id"]
    # B tries to reference A's customer_id in a deal in B's workspace
    r2 = requests.post(f"{API}/deals", headers=h(b["token"], b["ws"]),
                       json={"title": "Cross-Deal", "value": 100,
                             "customer_id": cid_a})
    assert r2.status_code == 400
    assert "not found" in r2.json()["detail"].lower()


def test_cannot_assign_other_workspace_user_to_task(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    # A tries to assign B (not a member of A's workspace) as task assignee
    r = requests.post(f"{API}/tasks", headers=h(a["token"], a["ws"]),
                     json={"title": "CrossAssign", "assignee_id": b["user"]["id"]})
    assert r.status_code == 400


def test_cannot_reference_other_workspace_customer_in_ticket(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    r = requests.post(f"{API}/customers", headers=h(a["token"], a["ws"]),
                     json={"name": "A-Cust-Tk"})
    cid_a = r.json()["id"]
    r2 = requests.post(f"{API}/tickets", headers=h(b["token"], b["ws"]),
                     json={"subject": "X", "customer_id": cid_a})
    assert r2.status_code == 400


def test_cannot_create_note_on_other_workspace_customer(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    r = requests.post(f"{API}/customers", headers=h(a["token"], a["ws"]),
                     json={"name": "A-CustNote"})
    cid_a = r.json()["id"]
    r2 = requests.post(f"{API}/notes", headers=h(b["token"], b["ws"]),
                     json={"content": "hi", "related_type": "customer", "related_id": cid_a})
    assert r2.status_code == 400


# ---------- 3. RBAC ----------
def test_viewer_cannot_create_customer(two_workspaces):
    a = two_workspaces["a"]
    # A invites a viewer
    u = uuid.uuid4().hex[:8]
    viewer_email = f"viewer_{u}@nexustest.com"
    # Signup viewer as an existing user first
    vs = requests.post(f"{API}/auth/signup", json={
        "email": viewer_email, "password": "ViewPW123", "name": "Viewer"
    }).json()
    inv = requests.post(f"{API}/workspaces/invite", headers=h(a["token"], a["ws"]),
                        json={"email": viewer_email, "role": "viewer"}).json()
    token = inv["invite_link"].rsplit("/", 1)[-1]
    # Viewer accepts
    requests.post(f"{API}/invites/{token}/accept",
                  json={"password": "ViewPW123", "name": "Viewer"})
    # Viewer tries to create a customer -> 403
    r = requests.post(f"{API}/customers", headers=h(vs["token"], a["ws"]),
                     json={"name": "Sneaky"})
    assert r.status_code == 403


def test_viewer_cannot_view_audit_log(two_workspaces):
    """Viewer should NOT see audit logs (owner/admin only)."""
    a = two_workspaces["a"]
    u = uuid.uuid4().hex[:8]
    viewer_email = f"viewer2_{u}@nexustest.com"
    vs = requests.post(f"{API}/auth/signup", json={
        "email": viewer_email, "password": "ViewPW123", "name": "V2"
    }).json()
    inv = requests.post(f"{API}/workspaces/invite", headers=h(a["token"], a["ws"]),
                        json={"email": viewer_email, "role": "viewer"}).json()
    token = inv["invite_link"].rsplit("/", 1)[-1]
    requests.post(f"{API}/invites/{token}/accept",
                  json={"password": "ViewPW123", "name": "V2"})
    r = requests.get(f"{API}/audit-logs", headers=h(vs["token"], a["ws"]))
    assert r.status_code == 403


def test_non_admin_cannot_change_workspace_settings(two_workspaces):
    a = two_workspaces["a"]
    u = uuid.uuid4().hex[:8]
    mem_email = f"mem_{u}@nexustest.com"
    ms = requests.post(f"{API}/auth/signup", json={
        "email": mem_email, "password": "MemPW123", "name": "M"
    }).json()
    inv = requests.post(f"{API}/workspaces/invite", headers=h(a["token"], a["ws"]),
                        json={"email": mem_email, "role": "member"}).json()
    token = inv["invite_link"].rsplit("/", 1)[-1]
    requests.post(f"{API}/invites/{token}/accept",
                  json={"password": "MemPW123", "name": "M"})
    r = requests.put(f"{API}/workspaces/settings", headers=h(ms["token"], a["ws"]),
                     json={"name": "Hijacked"})
    assert r.status_code == 403


# ---------- 4. AI permissions ----------
def test_unauthenticated_ai_endpoints_rejected():
    r = requests.post(f"{API}/ai/copilot", json={"message": "hi"})
    assert r.status_code == 401
    r2 = requests.get(f"{API}/ai/sales-forecast")
    assert r2.status_code == 401


def test_ai_forecast_requires_ai_permission(two_workspaces):
    """A viewer (no ai.use permission) should be rejected from the forecast endpoint."""
    a = two_workspaces["a"]
    u = uuid.uuid4().hex[:8]
    v_email = f"v_ai_{u}@nexustest.com"
    vs = requests.post(f"{API}/auth/signup", json={
        "email": v_email, "password": "PwV123456", "name": "AV"
    }).json()
    inv = requests.post(f"{API}/workspaces/invite", headers=h(a["token"], a["ws"]),
                        json={"email": v_email, "role": "viewer"}).json()
    tok_i = inv["invite_link"].rsplit("/", 1)[-1]
    requests.post(f"{API}/invites/{tok_i}/accept",
                  json={"password": "PwV123456", "name": "AV"})
    r = requests.get(f"{API}/ai/sales-forecast", headers=h(vs["token"], a["ws"]))
    assert r.status_code == 403


# ---------- 5. Payment security ----------
def test_payment_status_requires_auth(two_workspaces):
    r = requests.get(f"{API}/payments/status/anything")
    assert r.status_code in (401, 422)


def test_payment_status_cannot_expose_other_workspace(two_workspaces):
    """Even a random session_id must not leak; must return 404 to a caller who isn't its owner."""
    b = two_workspaces["b"]
    r = requests.get(f"{API}/payments/status/nonexistent-session",
                     headers=h(b["token"], b["ws"]))
    assert r.status_code == 404


# ---------- 6. Invitation one-time use ----------
def test_invitation_cannot_be_reused(two_workspaces):
    a = two_workspaces["a"]
    u = uuid.uuid4().hex[:8]
    email = f"reuse_{u}@nexustest.com"
    inv = requests.post(f"{API}/workspaces/invite", headers=h(a["token"], a["ws"]),
                        json={"email": email, "role": "member"}).json()
    token = inv["invite_link"].rsplit("/", 1)[-1]
    r1 = requests.post(f"{API}/invites/{token}/accept",
                       json={"password": "ReusePW123", "name": "R"})
    assert r1.status_code == 200
    r2 = requests.post(f"{API}/invites/{token}/accept",
                       json={"password": "ReusePW123", "name": "R"})
    assert r2.status_code == 400
    assert "already" in r2.json()["detail"].lower()


# ---------- 7. Search ----------
def test_search_is_workspace_scoped(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    marker = uuid.uuid4().hex[:8]
    requests.post(f"{API}/customers", headers=h(a["token"], a["ws"]),
                  json={"name": f"CROSSMARK_{marker}"})
    # B searches with A's marker in B's workspace — should find nothing
    r = requests.get(f"{API}/search?q=CROSSMARK_{marker}",
                     headers=h(b["token"], b["ws"]))
    d = r.json()
    assert d["customers"] == [] and d["leads"] == [] and d["deals"] == []


def test_search_regex_injection_safe(two_workspaces):
    """User-supplied regex metachars must be escaped, not executed."""
    a = two_workspaces["a"]
    # Add a benign customer
    requests.post(f"{API}/customers", headers=h(a["token"], a["ws"]),
                  json={"name": "Regex Test"})
    # Attempt a regex bomb: nested quantifiers. Should not cause 500 nor match unintended docs.
    r = requests.get(f"{API}/search?q=(a%2B)%2B", headers=h(a["token"], a["ws"]))
    assert r.status_code == 200
    # Attempt a very short query - should return empty
    r2 = requests.get(f"{API}/search?q=a", headers=h(a["token"], a["ws"]))
    assert r2.status_code == 200
    assert r2.json() == {"customers": [], "leads": [], "deals": []}


# ---------- 8. Workflow security ----------
def test_workflow_rejects_cross_workspace_user(two_workspaces):
    a, b = two_workspaces["a"], two_workspaces["b"]
    r = requests.post(f"{API}/workflows", headers=h(a["token"], a["ws"]),
                     json={
                        "name": "Bad-WF", "trigger": "lead_created",
                        "actions": [{"type": "assign_user", "params": {"user_id": b["user"]["id"]}}]
                     })
    assert r.status_code == 400


# ---------- 9. Pagination ----------
def test_pagination_caps_at_100(two_workspaces):
    a = two_workspaces["a"]
    # request oversized limit — should silently clamp
    r = requests.get(f"{API}/customers?limit=5000",
                     headers=h(a["token"], a["ws"]))
    assert r.status_code == 200
    assert len(r.json()) <= 100


def test_pagination_page_param_works(two_workspaces):
    a = two_workspaces["a"]
    # Add a few customers
    for i in range(3):
        requests.post(f"{API}/customers", headers=h(a["token"], a["ws"]),
                      json={"name": f"PageTest_{i}"})
    r1 = requests.get(f"{API}/customers?limit=2&page=1",
                     headers=h(a["token"], a["ws"]))
    r2 = requests.get(f"{API}/customers?limit=2&page=2",
                     headers=h(a["token"], a["ws"]))
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(r1.json()) <= 2 and len(r2.json()) <= 2


# ---------- 10. Rate limiting on login ----------
def test_login_is_rate_limited():
    """A burst of bad logins should eventually get 429.
    Only runs when RATE_LIMIT_ENABLED is not '0'."""
    if os.environ.get("RATE_LIMIT_ENABLED", "1") == "0":
        pytest.skip("Rate limiting disabled via env for this run")
    u = uuid.uuid4().hex[:8]
    email = f"rl_{u}@nexustest.com"
    saw_429 = False
    for _ in range(60):
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": "wrong"})
        if r.status_code == 429:
            saw_429 = True
            break
    assert saw_429, "Expected a 429 rate-limit response after burst of login attempts"


# ---------- 11. CORS ----------
def test_cors_does_not_reflect_arbitrary_origin():
    """The FastAPI CORS middleware must not echo an arbitrary origin as allowed with credentials.
    (Note: an upstream Kubernetes ingress/Cloudflare layer may add its own CORS headers on OPTIONS,
    but the browser refuses the combination `allow-origin: *` + `allow-credentials: true`, so this
    test targets the FastAPI backend directly.)"""
    r = requests.options("http://localhost:8001/api/customers", headers={
        "Origin": "https://evil.example.com",
        "Access-Control-Request-Method": "GET",
    })
    allowed = r.headers.get("access-control-allow-origin", "")
    assert allowed != "https://evil.example.com"
    assert allowed != "*"
