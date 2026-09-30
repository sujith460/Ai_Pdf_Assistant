"""PDF processing and OCR service module.

Renders every page of a PDF document into an image pixmap and passes the complete
page image to Tesseract OCR via pytesseract. This ensures comprehensive coverage
across normal text PDFs, scanned/image PDFs, and mixed pages containing both
selectable text and embedded images containing text.
"""

import io
import os
import re
import shutil
from pathlib import Path
from typing import Optional

import pymupdf
import pytesseract
from PIL import Image


class PDFServiceError(Exception):
    """Base exception for PDF service operations."""

    pass


class PDFNotFoundError(PDFServiceError):
    """Raised when the specified PDF file cannot be found on disk."""

    pass


class PDFProcessingError(PDFServiceError):
    """Raised when opening, reading, or rendering a PDF file fails."""

    pass


class TesseractNotFoundError(PDFServiceError):
    """Raised when Tesseract OCR is not installed or configured on the system."""

    pass


def get_tesseract_cmd() -> Optional[str]:
    """Locate Tesseract OCR executable on the system.

    Checks:
    1. TESSERACT_CMD environment variable
    2. System PATH via shutil.which
    3. Standard Windows installation paths
    """
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd and os.path.isfile(env_cmd):
        return env_cmd

    which_cmd = shutil.which("tesseract")
    if which_cmd:
        return which_cmd

    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        possible_windows_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.join(local_appdata, r"Programs\Tesseract-OCR\tesseract.exe"),
        ]
        for path in possible_windows_paths:
            if path and os.path.isfile(path):
                return path

    return None


def clean_extracted_text(text: str) -> str:
    """Clean and normalize extracted OCR text.

    Removes excessive horizontal whitespace and normalizes paragraph spacing
    without modifying meaningful document content or sentence structures.
    """
    if not text:
        return ""

    # Normalize newline characters (\r\n -> \n, \r -> \n)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Clean line-by-line whitespace: convert tabs & multi-spaces to single space
    cleaned_lines = [re.sub(r"[ \t]+", " ", line.strip()) for line in text.split("\n")]

    # Rejoin lines
    joined_text = "\n".join(cleaned_lines)

    # Preserve paragraph boundaries by collapsing 3+ consecutive newlines to 2
    normalized_text = re.sub(r"\n{3,}", "\n\n", joined_text)

    return normalized_text.strip()


def ocr_page_image(page: pymupdf.Page, dpi: int = 200) -> str:
    """Render a single PDF page to an image pixmap and run Tesseract OCR on the complete page.

    Args:
        page: PyMuPDF Page object.
        dpi: Resolution for rendering page image pixmap (default: 200 DPI).

    Returns:
        Extracted OCR text string for the rendered page.
    """
    pix = page.get_pixmap(dpi=dpi)
    image_bytes = pix.tobytes("png")
    image = Image.open(io.BytesIO(image_bytes))
    return pytesseract.image_to_string(image)


def extract_text_from_pdf(file_path: str | Path, dpi: int = 200) -> str:
    """Extract text from a PDF file by rendering every page as an image and running OCR.

    Pipeline:
    PDF
     ↓
    Render every PDF page as an image (PyMuPDF get_pixmap)
     ↓
    Tesseract OCR (pytesseract image_to_string)
     ↓
    Extract text from every page in original order
     ↓
    Clean extracted text (clean_extracted_text)
     ↓
    Return complete document text

    Args:
        file_path: File system path to the PDF document.
        dpi: Page rendering resolution in DPI (default: 200).

    Returns:
        Cleaned OCR text extracted from all pages in original order.

    Raises:
        PDFNotFoundError: If the file path does not exist.
        TesseractNotFoundError: If Tesseract OCR executable is missing.
        PDFProcessingError: If PDF rendering or OCR execution fails.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise PDFNotFoundError(f"PDF file not found at path: '{path}'")

    tesseract_cmd = get_tesseract_cmd()
    if not tesseract_cmd:
        raise TesseractNotFoundError(
            "Tesseract OCR is required for PDF text processing, but Tesseract is not installed or configured on your system.\n"
            "System requirement details:\n"
            "  1. Install Tesseract OCR for Windows from: https://github.com/UB-Mannheim/tesseract/wiki\n"
            "  2. Add Tesseract to system PATH or set the 'TESSERACT_CMD' environment variable pointing to tesseract.exe."
        )

    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    try:
        doc = pymupdf.open(str(path))
    except Exception as e:
        raise PDFProcessingError(
            f"Failed to open PDF file '{path.name}': {str(e)}"
        ) from e

    try:
        page_ocr_texts = []
        for page_num, page in enumerate(doc, start=1):
            try:
                page_text = ocr_page_image(page, dpi=dpi)
                if page_text:
                    page_ocr_texts.append(page_text)
            except (pytesseract.TesseractNotFoundError, FileNotFoundError) as e:
                raise TesseractNotFoundError(
                    "Tesseract OCR executable was not found when executing pytesseract.\n"
                    "Please verify that Tesseract is properly installed on your system."
                ) from e
            except Exception as e:
                raise PDFProcessingError(
                    f"OCR execution failed on page {page_num} of '{path.name}': {str(e)}"
                ) from e

        combined_text = "\n\n".join(page_ocr_texts)
        return clean_extracted_text(combined_text)
    finally:
        doc.close()


# Alias for API consistency
extract_pdf_text = extract_text_from_pdf
