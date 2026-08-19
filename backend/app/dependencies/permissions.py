"""RBAC permission matrix and dependencies."""
from fastapi import Depends, HTTPException

from app.dependencies.tenant import require_workspace

ROLES = ("owner", "admin", "manager", "member", "support", "viewer")
ROLE_LABELS = {
    "owner": "Super Admin",
    "admin": "Organization Admin",
    "manager": "Sales Manager",
    "member": "Sales Representative",
    "support": "Support Agent",
    "viewer": "Viewer",
}

# resource -> action -> set(role)
PERMISSIONS: dict = {
    "customer":     {"view": {"owner","admin","manager","member","support","viewer"}, "create": {"owner","admin","manager","member"}, "edit": {"owner","admin","manager","member"}, "delete": {"owner","admin"}, "assign": {"owner","admin","manager"}},
    "lead":         {"view": {"owner","admin","manager","member","viewer"},           "create": {"owner","admin","manager","member"}, "edit": {"owner","admin","manager","member"}, "delete": {"owner","admin"}, "assign": {"owner","admin","manager"}},
    "deal":         {"view": {"owner","admin","manager","member","viewer"},           "create": {"owner","admin","manager","member"}, "edit": {"owner","admin","manager","member"}, "delete": {"owner","admin"}, "assign": {"owner","admin","manager"}},
    "task":         {"view": {"owner","admin","manager","member","support","viewer"}, "create": {"owner","admin","manager","member","support"}, "edit": {"owner","admin","manager","member","support"}, "delete": {"owner","admin","manager","member","support"}},
    "note":         {"view": {"owner","admin","manager","member","support","viewer"}, "create": {"owner","admin","manager","member","support"}},
    "ticket":       {"view": {"owner","admin","manager","support","viewer"},           "create": {"owner","admin","manager","support","member"}, "edit": {"owner","admin","manager","support"}, "delete": {"owner","admin"}, "assign": {"owner","admin","manager","support"}},
    "settings":     {"view": {"owner","admin","manager"}, "manage": {"owner","admin"}},
    "audit_log":    {"view": {"owner","admin"}},
    "billing":      {"view": {"owner","admin"}, "manage": {"owner"}},
    "member":       {"view": {"owner","admin","manager","member","support","viewer"}, "invite": {"owner","admin"}, "manage": {"owner","admin"}},
    "ai":           {"use":  {"owner","admin","manager","member","support"}},
    "report":       {"view": {"owner","admin","manager","viewer"}, "export": {"owner","admin","manager"}},
}


def can(role: str, resource: str, action: str) -> bool:
    return role in PERMISSIONS.get(resource, {}).get(action, set())


def require_perm(resource: str, action: str):
    async def _dep(ctx: dict = Depends(require_workspace)):
        if not can(ctx["role"], resource, action):
            raise HTTPException(403, f"Missing permission: {resource}.{action}")
        return ctx
    return _dep


def require_role(*roles: str):
    async def _dep(ctx: dict = Depends(require_workspace)):
        if ctx["role"] not in roles:
            raise HTTPException(403, f"Requires role: {', '.join(roles)}")
        return ctx
    return _dep
