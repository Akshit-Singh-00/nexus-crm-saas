from typing import List, Optional, Literal
from pydantic import BaseModel


class CustomerIn(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Literal["active", "churned", "prospect"] = "active"
    tags: List[str] = []
