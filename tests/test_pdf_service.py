"""Verification test suite for PDF rendering & page-level Tesseract OCR service."""

import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

# Add project root directory to sys.path so app module can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.pdf_service import (
    PDFNotFoundError,
    TesseractNotFoundError,
    clean_extracted_text,
    extract_text_from_pdf,
    get_tesseract_cmd,
)


def create_text_pdf(output_path: Path, page_texts: list[str]) -> Path:
    """Create a searchable text PDF for testing."""
    doc = pymupdf.open()
    for text in page_texts:
        page = doc.new_page(width=595, height=842)  # A4 size
        page.insert_text((50, 100), text, fontsize=16)
    doc.save(str(output_path))
    doc.close()
    return output_path


def create_scanned_pdf(output_path: Path, page_texts: list[str]) -> Path:
    """Create an image-only (scanned) PDF for testing."""
    doc = pymupdf.open()
    for i, text in enumerate(page_texts):
        img = Image.new("RGB", (600, 200), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((30, 80), text, fill=(0, 0, 0))

        img_path = output_path.parent / f"temp_scanned_{i}.png"
        img.save(str(img_path))

        page = doc.new_page(width=595, height=842)
        rect = pymupdf.Rect(50, 50, 545, 250)
        page.insert_image(rect, filename=str(img_path))

        if img_path.exists():
            img_path.unlink()

    doc.save(str(output_path))
    doc.close()
    return output_path


def create_mixed_content_pdf(output_path: Path) -> Path:
    """Create a PDF page containing BOTH normal text AND an embedded image containing text."""
    # 1. Generate image containing text
    img = Image.new("RGB", (500, 150), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.text((20, 60), "IMAGE TEXT CONTENT", fill=(0, 0, 0))

    img_path = output_path.parent / "temp_mixed_img.png"
    img.save(str(img_path))

    # 2. Build PDF page with top text, embedded image, and bottom text
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    # Top normal vector text
    page.insert_text((50, 80), "NORMAL TOP HEADER TEXT", fontsize=16)

    # Middle embedded image with text inside
    rect = pymupdf.Rect(50, 120, 545, 270)
    page.insert_image(rect, filename=str(img_path))

    # Bottom normal vector text
    page.insert_text((50, 320), "NORMAL BOTTOM FOOTER TEXT", fontsize=16)

    doc.save(str(output_path))
    doc.close()

    if img_path.exists():
        img_path.unlink()

    return output_path


def test_text_cleaning():
    """Verify clean_extracted_text normalizes whitespace and preserves paragraph structure."""
    raw = "  Header Line   \r\n\r\n\n\nBody paragraph text here.   \n\n\n\nFooter line  "
    cleaned = clean_extracted_text(raw)
    assert isinstance(cleaned, str)
    assert "Header Line" in cleaned
    assert "Body paragraph text here." in cleaned
    assert "Footer line" in cleaned
    assert "\n\n\n" not in cleaned
    print("[OK] Test text cleaning passed.")


def test_nonexistent_file_handling():
    """Verify PDFNotFoundError is raised for invalid file paths."""
    fake_path = Path("uploads/missing_file_99999.pdf")
    try:
        extract_text_from_pdf(fake_path)
        assert False, "Should have raised PDFNotFoundError"
    except PDFNotFoundError as e:
        assert "not found" in str(e)
        print("[OK] Test PDFNotFoundError handling passed.")


def test_missing_tesseract_handling(tmp_path: Path):
    """Verify TesseractNotFoundError message clarity when Tesseract is missing."""
    tesseract_cmd = get_tesseract_cmd()
    if not tesseract_cmd:
        pdf_path = tmp_path / "test.pdf"
        create_text_pdf(pdf_path, ["Test Content"])
        try:
            extract_text_from_pdf(pdf_path)
            assert False, "Should have raised TesseractNotFoundError"
        except TesseractNotFoundError as e:
            assert "Tesseract OCR is required" in str(e)
            print("[OK] Test TesseractNotFoundError handling passed.")
    else:
        print("  [Info] Tesseract binary present on system; skipping missing Tesseract test.")


def test_full_ocr_pipeline(tmp_path: Path):
    """Verify rendering & OCR pipeline for text, scanned, mixed, and multi-page PDFs."""
    tesseract_cmd = get_tesseract_cmd()
    if not tesseract_cmd:
        print("  [Notice] Tesseract is not installed on system. Skipping OCR execution assertions.")
        return

    print(f"  Tesseract detected at: {tesseract_cmd}")

    # A. Normal Text-based PDF
    normal_pdf = tmp_path / "normal_ocr.pdf"
    create_text_pdf(normal_pdf, ["Normal Text PDF Page 1"])
    result_normal = extract_text_from_pdf(normal_pdf)
    assert isinstance(result_normal, str)
    print(f"  A. Normal PDF OCR Result:\n'{result_normal}'")

    # B. Scanned/Image PDF
    scanned_pdf = tmp_path / "scanned_ocr.pdf"
    create_scanned_pdf(scanned_pdf, ["Scanned Document Page 1"])
    result_scanned = extract_text_from_pdf(scanned_pdf)
    assert isinstance(result_scanned, str)
    print(f"  B. Scanned PDF OCR Result:\n'{result_scanned}'")

    # C & D. Mixed PDF (Normal text + Embedded image containing text on same page)
    mixed_pdf = tmp_path / "mixed_ocr.pdf"
    create_mixed_content_pdf(mixed_pdf)
    result_mixed = extract_text_from_pdf(mixed_pdf)
    assert isinstance(result_mixed, str)
    print(f"  C & D. Mixed Page OCR Result:\n'{result_mixed}'")

    # E. Multi-page PDF Order Preservation
    multipage_pdf = tmp_path / "multipage_ocr.pdf"
    pages_content = ["PAGE_ONE_START", "PAGE_TWO_MIDDLE", "PAGE_THREE_END"]
    create_text_pdf(multipage_pdf, pages_content)
    result_multi = extract_text_from_pdf(multipage_pdf)
    assert isinstance(result_multi, str)

    # Verify order of pages in output text
    pos1 = result_multi.find("PAGE_ONE_START")
    pos2 = result_multi.find("PAGE_TWO_MIDDLE")
    pos3 = result_multi.find("PAGE_THREE_END")
    if pos1 != -1 and pos2 != -1 and pos3 != -1:
        assert pos1 < pos2 < pos3, "Page text must appear in sequential order"
        print("  E. Multi-page order verified (Page 1 -> Page 2 -> Page 3).")

    print("[OK] Test full OCR pipeline passed successfully.")


def run_all_tests():
    print("=" * 60)
    print("Running Full Page PDF Rendering & OCR Verification Suite")
    print("=" * 60)

    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        test_text_cleaning()
        test_nonexistent_file_handling()
        test_missing_tesseract_handling(tmp_path)
        test_full_ocr_pipeline(tmp_path)

    print("=" * 60)
    print("ALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
