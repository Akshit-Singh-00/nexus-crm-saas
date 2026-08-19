"""CSV import preview + execute."""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.database import db
from app.core.rate_limit import limiter
from app.dependencies.permissions import can
from app.dependencies.tenant import require_workspace
from app.schemas.imports import ImportExecuteIn, ImportPreviewIn
from app.services.audit_service import audit
from app.services.import_service import (
    CUSTOMER_FIELDS,
    LEAD_FIELDS,
    infer_mapping,
    parse_csv,
)
from app.utils.ids import new_id, now_iso

router = APIRouter()


@router.post("/import/preview")
@limiter.limit("120/hour")
async def import_preview(request: Request, body: ImportPreviewIn, ctx: dict = Depends(require_workspace)):
    if body.entity == "lead" and not can(ctx["role"], "lead", "create"):
        raise HTTPException(403, "Missing permission: lead.create")
    if body.entity == "customer" and not can(ctx["role"], "customer", "create"):
        raise HTTPException(403, "Missing permission: customer.create")
    headers, data_rows = parse_csv(body.csv_text)
    fields = CUSTOMER_FIELDS if body.entity == "customer" else LEAD_FIELDS
    return {
        "headers": headers,
        "sample_rows": [dict(zip(headers, r + [""] * (len(headers) - len(r)))) for r in data_rows[:5]],
        "total_rows": len(data_rows),
        "target_fields": fields,
        "suggested_mapping": infer_mapping(headers, body.entity),
    }


@router.post("/import/execute")
@limiter.limit("30/hour")
async def import_execute(request: Request, body: ImportExecuteIn, ctx: dict = Depends(require_workspace)):
    if body.entity == "lead" and not can(ctx["role"], "lead", "create"):
        raise HTTPException(403, "Missing permission: lead.create")
    if body.entity == "customer" and not can(ctx["role"], "customer", "create"):
        raise HTTPException(403, "Missing permission: customer.create")
    headers, data_rows = parse_csv(body.csv_text)
    if len(data_rows) > 5000:
        raise HTTPException(400, f"Too many rows ({len(data_rows)}). Maximum 5000 per import.")
    fields = CUSTOMER_FIELDS if body.entity == "customer" else LEAD_FIELDS
    coll = db.customers if body.entity == "customer" else db.leads
    inserted = 0
    errors = []
    for i, row in enumerate(data_rows):
        try:
            row_dict = dict(zip(headers, row + [""] * (len(headers) - len(row))))
            entity_data = {}
            for csv_col, field in body.mapping.items():
                if field not in fields:
                    continue
                val = row_dict.get(csv_col, "").strip()
                if not val:
                    continue
                if field == "value":
                    try:
                        entity_data[field] = float(val)
                    except Exception:
                        entity_data[field] = 0
                else:
                    entity_data[field] = val
            if not entity_data.get("name"):
                errors.append({"row": i + 2, "error": "Missing name"})
                continue
            if body.entity == "customer":
                entity_data.setdefault("status", "active")
                entity_data.setdefault("tags", [])
            else:
                entity_data.setdefault("status", "new")
                entity_data.setdefault("source", "csv_import")
                entity_data.setdefault("value", 0)
                entity_data.setdefault("score", None)
                entity_data.setdefault("classification", None)
            doc = {
                "id": new_id(),
                "workspace_id": ctx["workspace_id"],
                "created_by": ctx["user"]["id"],
                "created_at": now_iso(),
                "updated_at": now_iso(),
                **entity_data,
            }
            await coll.insert_one(doc)
            inserted += 1
        except Exception as e:
            errors.append({"row": i + 2, "error": str(e)})
    await audit(ctx, "imported", body.entity, "batch", after={"count": inserted, "errors": len(errors)})
    return {"inserted": inserted, "errors": errors, "total": len(data_rows)}
