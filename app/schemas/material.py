from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MaterialResponse(BaseModel):
    """Pydantic v2 schema for returning material file metadata."""

    id: int
    filename: str
    file_path: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
