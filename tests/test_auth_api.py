"""Automated unit and integration test suite for Authentication (Registration & Username Login)."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import Base, get_db
from app.main import app

# Use StaticPool with in-memory SQLite for test isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def reset_test_db():
    """Re-create clean database tables."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_user_registration_and_username_login():
    """Verify user registration and authentication using username."""
    reset_test_db()

    # 1. Register a new user
    reg_payload = {
        "username": "johndoe",
        "email": "johndoe@example.com",
        "password": "SecurePassword123!",
    }
    reg_response = client.post("/users", json=reg_payload)
    assert reg_response.status_code == 201
    user_data = reg_response.json()
    assert user_data["username"] == "johndoe"
    assert user_data["email"] == "johndoe@example.com"
    assert "id" in user_data
    print("[OK] Test user registration passed.")

    # 2. Login using username and password
    login_form = {
        "username": "johndoe",
        "password": "SecurePassword123!",
    }
    login_response = client.post("/auth/login", data=login_form)
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    token = token_data["access_token"]
    print("[OK] Test login with username passed.")

    # 3. Test invalid password login
    invalid_pwd_form = {
        "username": "johndoe",
        "password": "WrongPassword123!",
    }
    invalid_pwd_res = client.post("/auth/login", data=invalid_pwd_form)
    assert invalid_pwd_res.status_code == 401
    assert "Invalid username or password" in invalid_pwd_res.json()["detail"]
    print("[OK] Test invalid password rejection passed.")

    # 4. Test non-existent username login
    nonexistent_user_form = {
        "username": "nonexistent_user",
        "password": "SecurePassword123!",
    }
    nonexistent_res = client.post("/auth/login", data=nonexistent_user_form)
    assert nonexistent_res.status_code == 401
    assert "Invalid username or password" in nonexistent_res.json()["detail"]
    print("[OK] Test non-existent username rejection passed.")

    # 5. Access a protected endpoint using the username login token
    headers = {"Authorization": f"Bearer {token}"}
    protected_res = client.post("/materials/upload", headers=headers)
    # Should get 422/400 validation error for missing upload file, NOT 401 Unauthorized
    assert protected_res.status_code != 401
    print("[OK] Test JWT access token authorization passed.")


def run_all_auth_tests():
    print("=" * 60)
    print("Running Authentication & Username Login Test Suite")
    print("=" * 60)

    test_user_registration_and_username_login()

    print("=" * 60)
    print("ALL AUTHENTICATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_auth_tests()
