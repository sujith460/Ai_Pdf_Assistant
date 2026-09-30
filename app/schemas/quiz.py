"""Pydantic schemas for Quiz generation requests and public responses."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class QuestionOptionsSchema(BaseModel):
    """Schema representing the four multiple-choice options (A, B, C, D)."""

    A: str = Field(..., description="Option A text")
    B: str = Field(..., description="Option B text")
    C: str = Field(..., description="Option C text")
    D: str = Field(..., description="Option D text")


class QuestionResponse(BaseModel):
    """Public response schema for an individual quiz question.

    SECURITY NOTE: correct_answer is intentionally omitted from the public API
    response to preserve quiz integrity for future submission/scoring endpoints.
    """

    id: int = Field(..., description="Unique question ID")
    question_order: int = Field(..., description="1-based order of the question in the quiz")
    question: str = Field(..., description="The question statement text")
    options: QuestionOptionsSchema = Field(
        ..., description="Dictionary containing options A, B, C, and D"
    )
    explanation: str = Field(
        ..., description="Educational explanation for the question's concept"
    )


class QuizResponse(BaseModel):
    """Public response schema for the generated Quiz."""

    quiz_id: int = Field(..., description="Unique ID of the created Quiz")
    material_id: int = Field(..., description="ID of the source material document")
    total_questions: int = Field(..., description="Total count of questions generated")
    created_at: datetime = Field(..., description="Timestamp when quiz was generated")
    questions: List[QuestionResponse] = Field(
        ..., description="List of public question objects"
    )
