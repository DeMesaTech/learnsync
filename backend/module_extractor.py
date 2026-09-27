"""Extract searchable text from supported module document formats."""

from pathlib import Path
import re

from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx"}
CHUNK_SIZE = 2000
TOPIC_HEADER_PATTERN = re.compile(
    r"\b(topic|topics|subject matter|course content|content|lesson|course outline|weekly outline)\b",
    re.IGNORECASE,
)
OUTLINE_SECTION_PATTERN = re.compile(
    r"\b(course outline|course content|subject matter|learning plan|weekly outline|topics covered)\b",
    re.IGNORECASE,
)
STOP_SECTION_PATTERN = re.compile(
    r"\b(references|bibliography|grading system|course policies|consultation hours|course description)\b",
    re.IGNORECASE,
)
NUMBERED_TOPIC_PATTERN = re.compile(r"^(?:\d+(?:\.\d+)*[.)-]?\s+|(?:week|unit|lesson|topic)\s+\d+\s*[:.)-]?\s+)", re.IGNORECASE)


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_pdf(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    return [_clean_text(page.extract_text()) for page in reader.pages]


def _extract_docx(path: Path) -> list[str]:
    document = Document(str(path))
    fragments = [_clean_text(paragraph.text) for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            fragments.append(_clean_text(" | ".join(cell.text for cell in row.cells)))
    return fragments


def _extract_xlsx(path: Path) -> list[str]:
    workbook = load_workbook(str(path), read_only=True, data_only=True)
    try:
        fragments = []
        for worksheet in workbook.worksheets:
            for row in worksheet.iter_rows(values_only=True):
                values = [_clean_text(value) for value in row]
                values = [value for value in values if value]
                if values:
                    fragments.append(" | ".join(values))
        return fragments
    finally:
        workbook.close()


def _extract_pptx(path: Path) -> list[str]:
    presentation = Presentation(str(path))
    fragments = []
    for slide in presentation.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text = _clean_text(shape.text)
                if text:
                    fragments.append(text)
    return fragments


def extract_module_text(path: str | Path) -> dict[str, object]:
    """Return normalized chunks and metadata for a supported document."""
    document_path = Path(path)
    extension = document_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported module format. Use PDF, DOCX, XLSX, or PPTX.")

    extractors = {
        ".pdf": _extract_pdf,
        ".docx": _extract_docx,
        ".xlsx": _extract_xlsx,
        ".pptx": _extract_pptx,
    }
    fragments = [_clean_text(fragment) for fragment in extractors[extension](document_path)]
    text = "\n".join(fragment for fragment in fragments if fragment)
    chunks = [text[index:index + CHUNK_SIZE] for index in range(0, len(text), CHUNK_SIZE)]

    return {
        "chunks": chunks,
        "content_extracted": bool(text),
        "warning": None if text else "No extractable text was found in this file.",
    }


def _topic_candidate(value: str, require_label: bool = True) -> str | None:
    text = _clean_text(value).strip(" |\t-\u2022")
    if not text or len(text) < 3 or len(text) > 255:
        return None
    if require_label and not NUMBERED_TOPIC_PATTERN.match(text):
        return None
    if re.fullmatch(
        r"(?:topics?|course content|subject matter|content|lesson|week|unit|learning outcomes?|objectives?|activities|assessment|references)",
        text.strip(" :.-"),
        re.IGNORECASE,
    ):
        return None
    if re.fullmatch(r"(?:week|unit|lesson|topic)\s+\d+\s*[:.)-]?", text, re.IGNORECASE):
        return None
    return text


def _docx_syllabus_topics(path: Path) -> list[str]:
    document = Document(str(path))
    topics: list[str] = []

    for table in document.tables:
        rows = [
            ["\n".join(_clean_text(paragraph.text) for paragraph in cell.paragraphs if _clean_text(paragraph.text)) for cell in row.cells]
            for row in table.rows
        ]
        header_index = None
        topic_column = None
        for row_index, row in enumerate(rows[:4]):
            for column_index, cell in enumerate(row):
                if TOPIC_HEADER_PATTERN.search(cell):
                    header_index = row_index
                    topic_column = column_index
                    break
            if topic_column is not None:
                break

        if topic_column is not None and header_index is not None:
            topics_before_table = len(topics)
            for row in rows[header_index + 1:]:
                if topic_column >= len(row):
                    continue
                cell_text = row[topic_column]
                candidates = re.split(r"\n+", cell_text)
                for candidate in candidates:
                    topic = _topic_candidate(candidate, require_label=False)
                    if topic:
                        topics.append(topic)
            if len(topics) > topics_before_table:
                continue

        for row in rows:
            for column_index, cell in enumerate(row[:-1]):
                if re.match(r"^(?:week|unit|lesson)\s*\d+\b", cell, re.IGNORECASE):
                    for candidate in re.split(r"\n+", row[column_index + 1]):
                        topic = _topic_candidate(candidate, require_label=False)
                        if topic:
                            topics.append(topic)
                    break

    in_outline = False
    for paragraph in document.paragraphs:
        text = _clean_text(paragraph.text)
        if not text:
            continue
        if OUTLINE_SECTION_PATTERN.search(text):
            in_outline = True
            continue
        if in_outline and STOP_SECTION_PATTERN.search(text):
            in_outline = False
            continue
        if in_outline or paragraph.style.name.lower().startswith("heading"):
            for candidate in re.split(r"\n+", text):
                topic = _topic_candidate(candidate, require_label=not in_outline)
                if topic:
                    topics.append(topic)

    return _unique_topics(topics)


def _unique_topics(topics: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        normalized = topic.casefold()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(topic)
        if len(unique) >= 100:
            break
    return unique


def _pdf_syllabus_topics(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    topics: list[str] = []
    in_outline = False
    for page in reader.pages:
        for raw_line in (page.extract_text() or "").splitlines():
            text = _clean_text(raw_line)
            if OUTLINE_SECTION_PATTERN.search(text):
                in_outline = True
                continue
            if in_outline and STOP_SECTION_PATTERN.search(text):
                in_outline = False
                continue
            if in_outline or NUMBERED_TOPIC_PATTERN.match(text):
                topic = _topic_candidate(text)
                if topic:
                    topics.append(topic)
    return _unique_topics(topics)


def extract_syllabus_topics(path: str | Path) -> list[str]:
    """Extract numbered or week-labeled topics from a syllabus outline."""
    document_path = Path(path)
    extension = document_path.suffix.lower()
    if extension == ".docx":
        return _docx_syllabus_topics(document_path)
    if extension == ".pdf":
        return _pdf_syllabus_topics(document_path)
    raise ValueError("Syllabus topic extraction supports DOCX and PDF files.")