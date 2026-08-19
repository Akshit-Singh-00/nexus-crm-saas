from typing import Literal
from pydantic import BaseModel


class ImportPreviewIn(BaseModel):
    csv_text: str
    entity: Literal["customer", "lead"]


class ImportExecuteIn(BaseModel):
    csv_text: str
    entity: Literal["customer", "lead"]
    mapping: dict  # {csv_column_name: entity_field_name}
