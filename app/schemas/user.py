from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration requests."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique username for the user",
    )
    email: EmailStr = Field(
        ...,
        description="Valid email address for the user",
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (minimum 8 characters)",
    )


class UserResponse(BaseModel):
    """Safe schema for user response (excludes password & password_hash)."""

    id: int
    username: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
