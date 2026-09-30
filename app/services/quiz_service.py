"""Quiz orchestrator service module.

Coordinates material lookup validation, PDF rendering & Tesseract OCR text extraction,
Gemini LLM quiz JSON generation, payload validation, database persistence, and
public response mapping (securing correct_answer from public output).
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.quiz import Quiz, QuizQuestion
from app.schemas.quiz import QuestionOptionsSchema, QuestionResponse, QuizResponse
from app.services.gemini_service import (
    GeminiAPIError,
    GeminiAPIKeyMissingError,
    GeminiService,
    GeminiServiceError,
)
from app.services.pdf_service import (
    PDFNotFoundError,
    PDFProcessingError,
    TesseractNotFoundError,
    extract_text_from_pdf,
)

logger = logging.getLogger(__name__)


def validate_and_clean_quiz_payload(raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate and sanitize the quiz JSON payload returned by Gemini.

    Ensures:
    - Root object contains a "questions" list.
    - Each question contains non-empty question statement, options A/B/C/D,
      correct_answer in ('A', 'B', 'C', 'D'), and explanation.

    Raises:
        HTTPException: 502 Bad Gateway if the payload fails validation.
    """
    if not isinstance(raw_json, dict) or "questions" not in raw_json:
        logger.error("Quiz payload validation failed: Root JSON does not contain 'questions' list.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini generated malformed quiz output: Missing 'questions' container.",
        )

    questions_raw = raw_json.get("questions")
    if not isinstance(questions_raw, list) or len(questions_raw) == 0:
        logger.error("Quiz payload validation failed: 'questions' list is empty or not a list.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini generated malformed quiz output: Empty question list.",
        )

    validated_questions = []
    seen_questions = set()

    for idx, item in enumerate(questions_raw, start=1):
        if not isinstance(item, dict):
            continue

        q_text = str(item.get("question", "")).strip()
        options = item.get("options")
        correct_ans = str(item.get("correct_answer", "")).strip().upper()
        explanation = str(item.get("explanation", "")).strip()

        # Check required text fields
        if not q_text or not explanation:
            logger.warning(f"Question item {idx} missing question text or explanation. Skipping.")
            continue

        # Prevent duplicate questions
        normalized_q = q_text.lower()
        if normalized_q in seen_questions:
            continue
        seen_questions.add(normalized_q)

        # Validate options dict
        if not isinstance(options, dict):
            logger.warning(f"Question item {idx} options is not a dictionary. Skipping.")
            continue

        opt_a = str(options.get("A", "")).strip()
        opt_b = str(options.get("B", "")).strip()
        opt_c = str(options.get("C", "")).strip()
        opt_d = str(options.get("D", "")).strip()

        if not opt_a or not opt_b or not opt_c or not opt_d:
            logger.warning(f"Question item {idx} missing one or more required options (A, B, C, D). Skipping.")
            continue

        # Validate correct answer choice
        if correct_ans not in ("A", "B", "C", "D"):
            logger.warning(f"Question item {idx} has invalid correct_answer '{correct_ans}'. Skipping.")
            continue

        validated_questions.append({
            "question": q_text,
            "options": {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d},
            "correct_answer": correct_ans,
            "explanation": explanation,
        })

    if len(validated_questions) == 0:
        logger.error("Zero questions remained after validation.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gemini response contained no valid multiple-choice questions.",
        )

    return validated_questions


def generate_quiz_for_material(
    material: Material, db: Session, num_questions: int = 10
) -> QuizResponse:
    """Generate, validate, persist, and return a quiz for an authenticated material document.

    Args:
        material: Material ORM model instance.
        db: SQLAlchemy database session.
        num_questions: Target question count (default: 10).

    Returns:
        Public QuizResponse schema (correct_answer hidden).
    """
    logger.info(f"Starting quiz generation request for material_id={material.id}")

    # 1. Verify physical PDF file existence on disk
    file_path = Path(material.file_path)
    if not file_path.exists() or not file_path.is_file():
        logger.error(f"Material id={material.id} physical file missing at path: '{file_path}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physical PDF file associated with material '{material.filename}' was not found on server storage.",
        )

    # 2. Extract OCR text using existing pdf_service.py
    logger.info(f"Executing PDF rendering and OCR for material_id={material.id}")
    try:
        ocr_text = extract_text_from_pdf(file_path)
    except PDFNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except TesseractNotFoundError as e:
        logger.error(f"Tesseract OCR missing for material_id={material.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
    except PDFProcessingError as e:
        logger.error(f"PDF OCR processing error for material_id={material.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render or process PDF pages for OCR: {str(e)}",
        ) from e

    # 3. Validate extracted OCR text
    cleaned_ocr_text = ocr_text.strip()
    alnum_chars = len(re.sub(r"\W+", "", cleaned_ocr_text))
    logger.info(f"Material id={material.id} OCR completed. Extracted text length: {len(cleaned_ocr_text)} chars ({alnum_chars} alphanumeric).")

    if alnum_chars < 15:
        logger.warning(f"Material id={material.id} produced insufficient text ({alnum_chars} alnum chars). Aborting quiz generation.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to generate quiz: The uploaded PDF file contained no readable or meaningful text after OCR processing.",
        )

    # 4. Invoke Gemini API for Quiz JSON
    logger.info(f"Sending OCR text to Gemini AI for quiz generation (material_id={material.id})")
    try:
        gemini_service = GeminiService()
        quiz_json = gemini_service.generate_quiz_json(cleaned_ocr_text, num_questions=num_questions)
    except GeminiAPIKeyMissingError as e:
        logger.error("Gemini API Key missing on server")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gemini API key is not configured on the server. Please check environment configuration.",
        ) from e
    except GeminiAPIError as e:
        logger.error(f"Gemini API failure for material_id={material.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini AI Service error: {str(e)}",
        ) from e
    except GeminiServiceError as e:
        logger.error(f"Gemini service error for material_id={material.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quiz: {str(e)}",
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    # 5. Validate Gemini Quiz JSON output
    validated_questions = validate_and_clean_quiz_payload(quiz_json)
    logger.info(f"Successfully validated {len(validated_questions)} questions from Gemini response.")

    # 6. Database Persistence
    try:
        new_quiz = Quiz(
            material_id=material.id,
            user_id=material.user_id,
            total_questions=len(validated_questions),
        )
        db.add(new_quiz)
        db.commit()
        db.refresh(new_quiz)

        for i, q in enumerate(validated_questions, start=1):
            question_record = QuizQuestion(
                quiz_id=new_quiz.id,
                question_order=i,
                question_text=q["question"],
                option_a=q["options"]["A"],
                option_b=q["options"]["B"],
                option_c=q["options"]["C"],
                option_d=q["options"]["D"],
                correct_answer=q["correct_answer"],
                explanation=q["explanation"],
            )
            db.add(question_record)

        db.commit()
        db.refresh(new_quiz)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error persisting quiz records for material_id={material.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record generated quiz in database storage.",
        ) from e

    # 7. Map to public QuizResponse (excluding correct_answer)
    public_questions = [
        QuestionResponse(
            id=q.id,
            question_order=q.question_order,
            question=q.question_text,
            options=QuestionOptionsSchema(
                A=q.option_a,
                B=q.option_b,
                C=q.option_c,
                D=q.option_d,
            ),
            explanation=q.explanation,
        )
        for q in new_quiz.questions
    ]

    return QuizResponse(
        quiz_id=new_quiz.id,
        material_id=material.id,
        total_questions=new_quiz.total_questions,
        created_at=new_quiz.created_at,
        questions=public_questions,
    )
