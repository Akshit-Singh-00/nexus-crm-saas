"""CSV parsing + column-mapping helpers used by the import router."""
import csv
import io
from typing import List

from fastapi import HTTPException

CUSTOMER_FIELDS = ["name", "email", "phone", "company", "status"]
LEAD_FIELDS = ["name", "email", "phone", "company", "source", "status", "value"]


def parse_csv(csv_text: str) -> tuple:
    if not csv_text.strip():
        raise HTTPException(400, "Empty CSV")
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        raise HTTPException(400, "No rows in CSV")
    headers = [h.strip() for h in rows[0]]
    data_rows = [r for r in rows[1:] if any(c.strip() for c in r)]
    return headers, data_rows


def infer_mapping(headers: List[str], entity: str) -> dict:
    fields = CUSTOMER_FIELDS if entity == "customer" else LEAD_FIELDS
    result = {}
    for h in headers:
        low = h.lower().strip()
        for f in fields:
            if f == low or f in low or low in f:
                result[h] = f
                break
    return result
