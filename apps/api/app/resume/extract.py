"""Stage 1 of resume parsing: PDF bytes -> plain text (projectprep.md, D5).

Pure code, no AI: fast, free, and deterministic.
"""

import pymupdf

MAX_PAGES = 5
# Below this, the PDF is almost certainly a scanned image with no text layer.
MIN_TEXT_CHARS = 200


class ResumeExtractionError(ValueError):
    """The upload can't be turned into usable resume text. Message is user-facing."""


def extract_text(pdf_bytes: bytes) -> str:
    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:  # PyMuPDF raises several unrelated types for bad files
        raise ResumeExtractionError("This file is not a readable PDF") from e

    with doc:
        if doc.page_count > MAX_PAGES:
            raise ResumeExtractionError(f"Resume is longer than {MAX_PAGES} pages")
        # sort=True reads blocks top-to-bottom, left-to-right, so two-column
        # resumes don't interleave lines from both columns.
        text = "\n".join(page.get_text(sort=True) for page in doc)

    # Drop blank lines and trailing spaces: fewer tokens sent to the model.
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    if len(text) < MIN_TEXT_CHARS:
        raise ResumeExtractionError("No text found in the PDF. Is it a scanned image? Upload a text-based PDF.")
    return text
