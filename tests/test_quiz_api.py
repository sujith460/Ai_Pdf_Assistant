"""Automated unit and integration test suite for POST /materials/{id}/quiz endpoint."""

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
from app.models.quiz import Quiz, QuizQuestion
from app.models.user import User

# Use StaticPool with in-memory SQLite for test isolation across threads
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


def create_test_pdf(file_path: Path, text: str = "Standard test document for Quiz API generation.") -> Path:
    """Helper to generate a real searchable PDF file on disk."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), text, fontsize=14)
    doc.save(str(file_path))
    doc.close()
    return file_path


SAMPLE_QUIZ_JSON = {
    "questions": [
        {
            "question": f"Question {i} statement based on document content?",
            "options": {
                "A": f"Option A text {i}",
                "B": f"Option B text {i}",
                "C": f"Option C text {i}",
                "D": f"Option D text {i}",
            },
            "correct_answer": "B",
            "explanation": f"Explanation text for question {i}.",
        }
        for i in range(1, 11)
    ]
}


def test_quiz_unauthenticated():
    """Verify 401 Unauthorized for request missing JWT bearer token."""
    reset_test_db()
    response = client.post("/materials/1/quiz")
    assert response.status_code == 401
    assert "Not authenticated" in response.json().get("detail", "")
    print("[OK] Test unauthenticated quiz request passed.")


def test_quiz_invalid_token():
    """Verify 401 Unauthorized for request with invalid JWT token."""
    reset_test_db()
    headers = {"Authorization": "Bearer invalid_token_xyz_123"}
    response = client.post("/materials/1/quiz", headers=headers)
    assert response.status_code == 401
    print("[OK] Test invalid token quiz request passed.")


def test_quiz_nonexistent_material():
    """Verify 404 Not Found for non-existent material ID."""
    reset_test_db()
    db = TestingSessionLocal()
    user = User(username="user1", email="user1@example.com", password_hash=hash_password("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/materials/99999/quiz", headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json().get("detail", "").lower()
    print("[OK] Test non-existent material ID passed.")


def test_quiz_other_user_material(tmp_path: Path):
    """Verify 403 Forbidden when accessing material owned by another user."""
    reset_test_db()
    db = TestingSessionLocal()
    owner = User(username="owner", email="owner@example.com", password_hash=hash_password("password123"))
    other_user = User(username="other", email="other@example.com", password_hash=hash_password("password123"))
    db.add_all([owner, other_user])
    db.commit()
    db.refresh(owner)
    db.refresh(other_user)

    pdf_file = tmp_path / "owner_quiz_doc.pdf"
    create_test_pdf(pdf_file, "Owner document text.")

    material = Material(user_id=owner.id, filename="owner_quiz_doc.pdf", file_path=str(pdf_file))
    db.add(material)
    db.commit()
    db.refresh(material)

    other_token = create_access_token(data={"sub": str(other_user.id)})
    headers = {"Authorization": f"Bearer {other_token}"}

    response = client.post(f"/materials/{material.id}/quiz", headers=headers)
    assert response.status_code == 403
    assert "Access denied" in response.json().get("detail", "")
    print("[OK] Test forbidden material ownership check passed.")


def test_quiz_missing_physical_file(tmp_path: Path):
    """Verify 404 Not Found when DB record exists but physical PDF is missing from storage."""
    reset_test_db()
    db = TestingSessionLocal()
    user = User(username="file_test", email="file_test@example.com", password_hash=hash_password("password123"))
    db.add(user)
    db.commit()
    db.refresh(user)

    missing_path = tmp_path / "ghost_quiz_file.pdf"
    material = Material(user_id=user.id, filename="ghost_quiz_file.pdf", file_path=str(missing_path))
    db.add(material)
    db.commit()
    db.refresh(material)

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(f"/materials/{material.id}/quiz", headers=headers)
    assert response.status_code == 404
    assert "not found on server storage" in response.json().get("detail", "").lower()
    print("[OK] Test missing physical file handling passed.")


def test_quiz_insufficient_ocr_text(tmp_path: Path):
    """Verify 422 Unprocessable Entity when OCR produces empty or non-readable text."""
    reset_test_db()
    with patch("app.services.quiz_service.extract_text_from_pdf") as mock_ocr:
        mock_ocr.return_value = "   "  # Empty OCR text

        db = TestingSessionLocal()
        user = User(username="empty_ocr", email="empty_ocr@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)

        pdf_file = tmp_path / "empty_quiz_doc.pdf"
        create_test_pdf(pdf_file, "dummy")

        material = Material(user_id=user.id, filename="empty_quiz_doc.pdf", file_path=str(pdf_file))
        db.add(material)
        db.commit()
        db.refresh(material)

        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(f"/materials/{material.id}/quiz", headers=headers)
        assert response.status_code == 422
        assert "no readable or meaningful text" in response.json().get("detail", "").lower()
        print("[OK] Test insufficient OCR text handling passed.")


def test_quiz_malformed_gemini_json(tmp_path: Path):
    """Verify 502 Bad Gateway when Gemini returns invalid or malformed quiz JSON."""
    reset_test_db()
    with patch("app.services.quiz_service.GeminiService.generate_quiz_json") as mock_gemini:
        # Return malformed JSON structure missing required fields
        mock_gemini.return_value = {"invalid_key": "not a questions list"}

        db = TestingSessionLocal()
        user = User(username="malformed_user", email="malformed@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)

        pdf_file = tmp_path / "malformed_doc.pdf"
        create_test_pdf(pdf_file, "Lecture content for malformed test.")

        material = Material(user_id=user.id, filename="malformed_doc.pdf", file_path=str(pdf_file))
        db.add(material)
        db.commit()
        db.refresh(material)

        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(f"/materials/{material.id}/quiz", headers=headers)
        assert response.status_code == 502
        assert "malformed" in response.json().get("detail", "").lower()
        print("[OK] Test malformed Gemini JSON response handling passed.")


def test_quiz_successful_generation_and_db_persistence(tmp_path: Path):
    """Verify successful quiz generation, database persistence, and public response security."""
    reset_test_db()
    with patch("app.services.quiz_service.GeminiService.generate_quiz_json") as mock_gemini:
        mock_gemini.return_value = SAMPLE_QUIZ_JSON

        db = TestingSessionLocal()
        user = User(username="quiz_owner", email="quiz_owner@example.com", password_hash=hash_password("password123"))
        db.add(user)
        db.commit()
        db.refresh(user)

        pdf_file = tmp_path / "quiz_valid_doc.pdf"
        create_test_pdf(pdf_file, "Comprehensive lecture material on FastAPI, SQLAlchemy, and Tesseract OCR.")

        material = Material(user_id=user.id, filename="quiz_valid_doc.pdf", file_path=str(pdf_file))
        db.add(material)
        db.commit()
        db.refresh(material)

        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(f"/materials/{material.id}/quiz", headers=headers)
        assert response.status_code == 201
        data = response.json()

        # 1. Assert Response Structure
        assert data["material_id"] == material.id
        assert data["total_questions"] == 10
        assert len(data["questions"]) == 10

        # 2. SECURITY ASSERTION: correct_answer MUST NOT be in public response
        for q_resp in data["questions"]:
            assert "correct_answer" not in q_resp, "SECURITY FAILURE: correct_answer leaked in public API response!"
            assert "question" in q_resp
            assert "options" in q_resp
            assert set(q_resp["options"].keys()) == {"A", "B", "C", "D"}
            assert "explanation" in q_resp

        # 3. DATABASE PERSISTENCE ASSERTION: Verify Quiz & QuizQuestion records stored in SQLite
        db_quiz = db.query(Quiz).filter(Quiz.id == data["quiz_id"]).first()
        assert db_quiz is not None
        assert db_quiz.material_id == material.id
        assert db_quiz.user_id == user.id
        assert db_quiz.total_questions == 10

        db_questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == db_quiz.id).order_by(QuizQuestion.question_order).all()
        assert len(db_questions) == 10

        # DB Assertion: Verify correct_answer IS stored in the database for scoring
        for db_q in db_questions:
            assert db_q.correct_answer == "B"
            assert db_q.option_a != ""
            assert db_q.explanation != ""

        print("[OK] Test successful quiz generation, DB persistence, and answer security passed.")


def run_all_quiz_tests():
    print("=" * 60)
    print("Running Quiz API Test Suite")
    print("=" * 60)

    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        test_quiz_unauthenticated()
        test_quiz_invalid_token()
        test_quiz_nonexistent_material()
        test_quiz_other_user_material(tmp_path)
        test_quiz_missing_physical_file(tmp_path)
        test_quiz_insufficient_ocr_text(tmp_path)
        test_quiz_malformed_gemini_json(tmp_path)
        test_quiz_successful_generation_and_db_persistence(tmp_path)

    print("=" * 60)
    print("ALL QUIZ API TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_quiz_tests()
