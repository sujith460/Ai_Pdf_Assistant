import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.material import Material
from app.models.user import User
from app.schemas.material import MaterialResponse
from app.schemas.quiz import QuizResponse
from app.schemas.summary import SummaryResponse
from app.services.quiz_service import generate_quiz_for_material
from app.services.summary_service import generate_summary_for_material

router = APIRouter(prefix="/materials", tags=["Materials"])

UPLOAD_DIR = Path("uploads")


@router.post(
    "/upload",
    response_model=MaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF document",
    description="Upload an authenticated user's PDF document. The file is saved with a unique UUID filename.",
)
async def upload_material(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MaterialResponse:
    """Validate and upload a PDF document for the authenticated user."""
    # Validate PDF extension
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    # Validate PDF magic bytes header (%PDF)
    header = await file.read(4)
    await file.seek(0)
    if not header.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid PDF file format",
        )

    # Ensure upload directory exists
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Generate unique stored filename
    unique_filename = f"{uuid.uuid4().hex}.pdf"
    file_path_on_disk = UPLOAD_DIR / unique_filename
    relative_path = f"uploads/{unique_filename}"

    # Save file content to disk
    try:
        with open(file_path_on_disk, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded file to storage",
        ) from e

    # Create Material database record linked to current_user.id
    try:
        new_material = Material(
            user_id=current_user.id,
            filename=file.filename,
            file_path=relative_path,
        )
        db.add(new_material)
        db.commit()
        db.refresh(new_material)
    except Exception as e:
        # Clean up stored file if database transaction fails
        if file_path_on_disk.exists():
            file_path_on_disk.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record material metadata in database",
        ) from e

    return new_material


@router.post(
    "/{id}/summary",
    response_model=SummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI Summary for a Material",
    description="Renders PDF pages to images, extracts text via Tesseract OCR, and generates a structured summary using Gemini AI.",
)
def generate_material_summary_endpoint(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SummaryResponse:
    """Generate an AI summary for the specified material ID owned by the authenticated user."""
    # Find Material in database
    material = db.query(Material).filter(Material.id == id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {id} not found",
        )

    # Verify material ownership
    if material.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this material",
        )

    # Invoke summary service
    return generate_summary_for_material(material)


@router.post(
    "/{id}/quiz",
    response_model=QuizResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI Quiz for a Material",
    description="Renders PDF pages to images, extracts text via Tesseract OCR, generates a 10-question multiple-choice quiz using Gemini, stores the quiz & questions in SQLite, and returns the public quiz schema.",
)
def generate_material_quiz_endpoint(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuizResponse:
    """Generate, store, and return a 10-question multiple choice quiz for an authenticated user's material."""
    # Find Material in database
    material = db.query(Material).filter(Material.id == id).first()
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material with ID {id} not found",
        )

    # Verify material ownership
    if material.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this material",
        )

    # Invoke quiz service
    return generate_quiz_for_material(material, db)
