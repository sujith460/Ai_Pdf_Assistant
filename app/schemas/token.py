from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """OAuth2 standard token response schema."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema representing JWT decoded payload data."""

    user_id: Optional[int] = None
