import io
import uuid
import pytest
import pytest_asyncio

from app.services.pdf_processor import extract_text_from_pdf, validate_pdf


def _make_simple_pdf() -> bytes:
    """Create a minimal valid PDF for testing."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "This is a test PDF document with enough text content "
                     "to verify that extraction works correctly. Battery degradation "
                     "is an important topic in energy storage research. This paper "
                     "discusses state of health estimation methods for lithium-ion "
                     "batteries used in grid-scale applications.")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestPdfExtraction:
    def test_pdf_text_extraction(self):
        """Extract text from a small test PDF, assert > 100 chars."""
        pdf_bytes = _make_simple_pdf()
        text = extract_text_from_pdf(pdf_bytes)
        assert len(text) > 100
        assert "battery" in text.lower() or "Battery" in text

    def test_validate_pdf_valid(self):
        """Valid PDF passes validation."""
        pdf_bytes = _make_simple_pdf()
        error = validate_pdf(pdf_bytes, "test.pdf")
        assert error is None

    def test_pdf_rejected_if_not_pdf(self):
        """Non-PDF file is rejected."""
        txt_bytes = b"This is just a plain text file, not a PDF."
        error = validate_pdf(txt_bytes, "test.txt")
        assert error is not None
        assert "PDF" in error

    def test_pdf_rejected_if_too_large(self):
        """File over 50MB is rejected."""
        # Create a bytes object > 50MB
        large_bytes = b"%PDF-" + b"0" * (51 * 1024 * 1024)
        error = validate_pdf(large_bytes, "huge.pdf")
        assert error is not None
        assert "large" in error.lower()

    def test_pdf_rejected_bad_magic_bytes(self):
        """File with .pdf extension but wrong content is rejected."""
        fake_pdf = b"NOT_A_PDF_FILE_CONTENT"
        error = validate_pdf(fake_pdf, "fake.pdf")
        assert error is not None


class TestPdfUploadAPI:
    @pytest.mark.asyncio
    async def test_pdf_upload_endpoint(self, test_client, db_session):
        """POST with valid PDF returns 200, paper record updated."""
        from app.models.paper import Paper
        from app.auth import get_current_user
        from app.main import app

        user_id = uuid.uuid4()
        fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

        paper = Paper(
            id=uuid.uuid4(), title="PDF Upload Test", authors=["A"],
            journal="J", journal_source="rss", abstract="Test abstract.",
        )
        db_session.add(paper)
        await db_session.commit()

        app.dependency_overrides[get_current_user] = lambda: fake_user

        pdf_bytes = _make_simple_pdf()
        resp = await test_client.post(
            f"/api/v1/papers/{paper.id}/upload-pdf",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploaded"
        assert data["text_length"] > 100

        # Verify full_text was saved
        await db_session.refresh(paper)
        assert paper.full_text is not None
        assert len(paper.full_text) > 100

        del app.dependency_overrides[get_current_user]

    @pytest.mark.asyncio
    async def test_pdf_rejected_if_not_pdf_api(self, test_client, db_session):
        """POST with .txt file returns 400."""
        from app.models.paper import Paper
        from app.auth import get_current_user
        from app.main import app

        user_id = uuid.uuid4()
        fake_user = {"id": str(user_id), "email": "test@test.com", "role": "researcher"}

        paper = Paper(
            id=uuid.uuid4(), title="Reject Test", authors=["A"],
            journal="J", journal_source="rss",
        )
        db_session.add(paper)
        await db_session.commit()

        app.dependency_overrides[get_current_user] = lambda: fake_user

        resp = await test_client.post(
            f"/api/v1/papers/{paper.id}/upload-pdf",
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )
        assert resp.status_code == 400

        del app.dependency_overrides[get_current_user]
