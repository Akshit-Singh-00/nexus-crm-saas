from typing import Literal
from pydantic import BaseModel


class CheckoutRequestIn(BaseModel):
    plan_id: Literal["pro", "team"]
    origin_url: str
