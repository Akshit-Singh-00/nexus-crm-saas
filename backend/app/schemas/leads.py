from typing import Optional, Literal
from pydantic import BaseModel


class LeadIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = "manual"
    status: Literal["new", "contacted", "qualified", "unqualified"] = "new"
    value: float = 0
