"""Summary orchestrator service module.

Coordinates material lookup validation, PDF page rendering & OCR text extraction,
meaningful text validation, Gemini LLM summarization, and error handling.
"""

import logging
import re
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.material import Material
from app.schemas.summary import SummaryResponse
from app.services.gemini_service import (
    GeminiAPIError,
    GeminiAPIKeyMissingError,
    GeminiServiceError,
    generate_document_summary,
)
from app.services.pdf_service import (
    PDFNotFoundError,
    PDFProcessingError,
    TesseractNotFoundError,
    extract_text_from_pdf,
)

logger = logging.getLogger(__name__)


def generate_summary_for_material(material: Material) -> SummaryResponse:
    """Generate and return a summary for an authenticated user's uploaded material.

    Args:
        material: Material ORM model instance.

    Returns:
        SummaryResponse containing material_id, generated summary, and source mode.

    Raises:
        HTTPException: For missing files (404), unreadable/insufficient OCR (422),
                        missing Gemini API key (500), OCR errors (500),
                        or Gemini API failures (502).
    """
    logger.info(f"Starting summary generation request for material_id={material.id}")

    # 1. Validate physical PDF file path on disk
    file_path = Path(material.file_path)
    if not file_path.exists() or not file_path.is_file():
        logger.error(f"Material id={material.id} physical file missing at path: '{file_path}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physical PDF file associated with material '{material.filename}' was not found on server storage.",
        )

    # 2. Extract text from PDF via page-level image rendering and Tesseract OCR
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

    # 3. Validate extracted OCR text for meaningful content
    cleaned_ocr_text = ocr_text.strip()
    alnum_chars = len(re.sub(r"\W+", "", cleaned_ocr_text))
    logger.info(f"Material id={material.id} OCR completed. Extracted text length: {len(cleaned_ocr_text)} chars ({alnum_chars} alphanumeric).")

    if alnum_chars < 15:
        logger.warning(f"Material id={material.id} produced insufficient text ({alnum_chars} alnum chars). Aborting summary prompt.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to generate summary: The uploaded PDF file contained no readable or meaningful text after OCR processing.",
        )

    # 4. Generate summary using Gemini AI Service
    logger.info(f"Sending extracted OCR text ({len(cleaned_ocr_text)} chars) to Gemini AI for material_id={material.id}")
    try:
        summary_text = generate_document_summary(cleaned_ocr_text)
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
        logger.error(f"Gemini service failure for material_id={material.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}",
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    logger.info(f"Summary generation completed successfully for material_id={material.id}")

    return SummaryResponse(
        material_id=material.id,
        summary=summary_text,
        source="ocr",
    )
