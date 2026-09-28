"""
Resume text extraction service.
Validates file extension, MIME type, magic bytes, and file size.
Extracts text from PDF (via pypdf) and DOCX (via python-docx including tables and headers).
Enforces minimum character threshold (detecting scanned/image PDFs) and caps parser input length.
"""

import io
import logging
from fastapi import UploadFile, HTTPException, status
import pypdf
import docx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
DOCX_MAGIC = b"PK\x03\x04"
MIN_TEXT_CHARS = 200
MAX_PARSER_CHARS = 30000


class ResumeExtractService:
    @staticmethod
    async def validate_and_extract(file: UploadFile) -> tuple[str, bytes]:
        """
        Validates the uploaded file and extracts its raw text content.
        Returns:
            (extracted_text: str, file_bytes: bytes)
        Raises:
            HTTPException 400 for invalid formats, 413 for oversized files, 422 for scanned PDFs.
        """
        settings = get_settings()
        max_bytes = settings.max_resume_mb * 1024 * 1024

        filename = (file.filename or "").lower()
        if not (filename.endswith(".pdf") or filename.endswith(".docx")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file format. Only PDF (.pdf) and Word (.docx) documents are accepted.",
            )

        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )

        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.max_resume_mb} MB.",
            )

        # Validate magic bytes
        if filename.endswith(".pdf"):
            if not content.startswith(PDF_MAGIC):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File header does not match a valid PDF document.",
                )
            extracted_text = ResumeExtractService._extract_pdf(content)
        else:
            if not content.startswith(DOCX_MAGIC):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File header does not match a valid DOCX document.",
                )
            extracted_text = ResumeExtractService._extract_docx(content)

        clean_text = extracted_text.strip()

        # Check for scanned or empty PDFs
        if len(clean_text) < MIN_TEXT_CHARS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Text-based resume required. The uploaded document contains insufficient text "
                    "(under 200 characters), which usually indicates a scanned image or photograph. "
                    "Please upload a standard text PDF or DOCX resume."
                ),
            )

        # Cap text sent to parser at 30,000 characters
        capped_text = clean_text[:MAX_PARSER_CHARS]
        return capped_text, content

    @staticmethod
    def _extract_pdf(content: bytes) -> str:
        text_parts: list[str] = []
        try:
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    text_parts.append(txt)
        except Exception as e:
            logger.error("Failed to extract PDF text: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted or password-protected PDF document: {str(e)}",
            )
        return "\n".join(text_parts)

    @staticmethod
    def _extract_docx(content: bytes) -> str:
        text_parts: list[str] = []
        try:
            doc = docx.Document(io.BytesIO(content))
            # Header text
            for section in doc.sections:
                if section.header:
                    for p in section.header.paragraphs:
                        if p.text.strip():
                            text_parts.append(p.text.strip())

            # Paragraphs
            for p in doc.paragraphs:
                if p.text.strip():
                    text_parts.append(p.text.strip())

            # Tables
            for table in doc.tables:
                for row in table.rows:
                    row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if row_cells:
                        text_parts.append(" | ".join(row_cells))
        except Exception as e:
            logger.error("Failed to extract DOCX text: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted or invalid DOCX document: {str(e)}",
            )
        return "\n".join(text_parts)


resume_extract_service = ResumeExtractService()
