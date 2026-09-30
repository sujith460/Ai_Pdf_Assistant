from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.token import Token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=Token,
    summary="User login and JWT token generation",
    description="Authenticate user by username and password via OAuth2 form, returning a JWT bearer token.",
)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    """Authenticate user credentials and issue JWT access token."""
    # Query user by unique username
    user = db.query(User).filter(User.username == form_data.username).first()

    # Generic authentication error to avoid user enumeration attacks
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue access token with user.id stored in the sub (subject) claim
    access_token = create_access_token(data={"sub": str(user.id)})

    return Token(access_token=access_token, token_type="bearer")
