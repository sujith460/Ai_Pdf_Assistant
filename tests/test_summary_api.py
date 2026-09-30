"""Automated unit and integration test suite for POST /materials/{id}/summary endpoint."""

import sys
from pathlib import Path
from unittest.mock import patch

import pymupdf
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.security import create_access_token, hash_password
from app.database import Base, get_db
from app.main import app
from app.models.material import Material
from app.models.user import User

# Use StaticPool with in-memory SQLite so all sessions share the exact same database
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
    """Re-create clean tables for test isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_test_pdf(file_path: Path, text: str = "Standard test document for summary API.") -> Path:
    """Helper to generate a real PDF file on disk."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), text, fontsize=14)
    doc.save(str(file_path))
    doc.close()
    return file_path


def test_summary_unauthenticated():
    """Verify 401 Unauthorized for request missing JWT bearer token."""
    reset_test_db()
    response = client.post("/materials/1/summary")
    assert response.status_code == 401
    assert "Not authenticated" in response.json().get("detail", "")
    print("[OK] Test unauthenticated summary request passed.")


def test_summary_nonexistent_material(tmp_path: Path):
    """Verify 404 Not Found for non-existent material ID."""
    reset_test_db()
    db = TestingSessionLocal()
    user = User(username="user1", email="test_user1@example.com", password_hash=hash_password("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/materials/99999/summary", headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()
    print("[OK] Test non-existent material ID passed.")


def test_summary_other_user_material(tmp_path: Path):
    """Verify 403 Forbidden when accessing material owned by another user."""
    reset_test_db()
    db = TestingSessionLocal()
    owner = User(username="owner", email="owner@example.com", password_hash=hash_password("password123"))
    other_user = User(username="other", email="other@example.com", password_hash=hash_password("password123"))
    db.add_all([owner, other_user])
    db.commit()
    db.refresh(owner)
    db.refresh(other_user)

    pdf_file = tmp_path / "owner_doc.pdf"
    create_test_pdf(pdf_file, "Owner secret content.")

    material = Material(user_id=owner.id, filename="owner_doc.pdf", file_path=str(pdf_file))
    db.add(material)
    db.commit()
    db.refresh(material)

    other_token = create_access_token(data={"sub": str(other_user.id)})
    headers = {"Authorization": f"Bearer {other_token}"}

    response = client.post(f"/materials/{material.id}/summary", headers=headers)
    assert response.status_code == 403
    assert "Access denied" in response.json().get("detail", "")
    print("[OK] Test forbidden material ownership check passed.")


def test_summary_missing_physical_file(tmp_path: Path):
    """Verify 404 Not Found when DB record exists but physical PDF is missing from storage."""
    reset_test_db()
    db = TestingSessionLocal()
    user = User(username="file_test", email="file_test@example.com", password_hash=hash_password("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    missing_path = tmp_path / "ghost_file.pdf"  # File is never created on disk
    material = Material(user_id=user.id, filename="ghost_file.pdf", file_path=str(missing_path))
    db.add(material)
    db.commit()
    db.refresh(material)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(f"/materials/{material.id}/summary", headers=headers)
    assert response.status_code == 404
    assert "not found on server storage" in response.json().get("detail", "").lower()
    print("[OK] Test missing physical file handling passed.")


def test_summary_successful_generation(tmp_path: Path):
    """Verify successful summary generation for authenticated material owner."""
    reset_test_db()
    with patch("app.services.summary_service.generate_document_summary") as mock_gemini:
        mock_gemini.return_value = "This is a mock AI summary of the test document."

        db = TestingSessionLocal()
        user = User(username="valid_user", email="valid_user@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)

        pdf_file = tmp_path / "valid_doc.pdf"
        create_test_pdf(pdf_file, "Comprehensive academic lecture notes on FastAPI and Artificial Intelligence.")

        material = Material(user_id=user.id, filename="valid_doc.pdf", file_path=str(pdf_file))
        db.add(material)
        db.commit()
        db.refresh(material)

        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(f"/materials/{material.id}/summary", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["material_id"] == material.id
        assert data["summary"] == "This is a mock AI summary of the test document."
        assert data["source"] == "ocr"
        print("[OK] Test successful summary generation passed.")


def test_summary_insufficient_ocr_text(tmp_path: Path):
    """Verify 422 Unprocessable Entity when OCR produces empty or non-readable text."""
    reset_test_db()
    with patch("app.services.summary_service.extract_text_from_pdf") as mock_ocr:
        mock_ocr.return_value = "   "  # Empty whitespace text

        db = TestingSessionLocal()
        user = User(username="empty_ocr", email="empty_ocr@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)

        pdf_file = tmp_path / "empty_doc.pdf"
        create_test_pdf(pdf_file, "dummy")

        material = Material(user_id=user.id, filename="empty_doc.pdf", file_path=str(pdf_file))
        db.add(material)
        db.commit()
        db.refresh(material)

        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(f"/materials/{material.id}/summary", headers=headers)
        assert response.status_code == 422
        assert "no readable or meaningful text" in response.json().get("detail", "").lower()
        print("[OK] Test insufficient OCR text handling passed.")


def run_all_summary_tests():
    print("=" * 60)
    print("Running Summary API Test Suite")
    print("=" * 60)

    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        test_summary_unauthenticated()
        test_summary_nonexistent_material(tmp_path)
        test_summary_other_user_material(tmp_path)
        test_summary_missing_physical_file(tmp_path)
        test_summary_successful_generation(tmp_path)
        test_summary_insufficient_ocr_text(tmp_path)

    print("=" * 60)
    print("ALL SUMMARY API TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_summary_tests()
