"""Pydantic schemas for summary API requests and responses."""

from pydantic import BaseModel, Field


class SummaryResponse(BaseModel):
    """Response model for material document summary endpoint."""

    material_id: int = Field(..., description="Unique ID of the material document")
    summary: str = Field(..., description="Generated summary text of the document")
    source: str = Field(
        default="ocr",
        description="Source mode of text extraction used for summarization",
    )
