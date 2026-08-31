"""
Document loading and chunking service.

Supported formats: PDF, DOCX, TXT, MD, RST, CSV, XLSX, XLS
"""

import csv
import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    page: int | None = None


def _chunk_text(text: str, chunk_size: int = 600, overlap: int = 120) -> list[str]:
    """
    Split text into overlapping chunks, preferring natural boundaries
    (paragraph → newline → sentence → word → character).
    """
    if not text.strip():
        return []

    if overlap >= chunk_size:
        raise ValueError("Overlap must be less than chunk_size to ensure forward progress.")

    separators = ["\n\n", "\n", ". ", " "]
    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            for sep in separators:
                pos = text.rfind(sep, start, end)
                if pos != -1 and pos > start + overlap:
                    end = pos + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break
        start = end - overlap

    return chunks


def _load_pdf(content: bytes, chunk_size: int, overlap: int) -> list[TextChunk]:
    """Load PDF bytes and return chunks with page metadata."""
    try:
        import pypdf
    except ImportError:
        raise RuntimeError("pypdf is required for PDF support: pip install pypdf")

    reader = pypdf.PdfReader(io.BytesIO(content))
    chunks: list[TextChunk] = []
    chunk_index = 0

    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue
        for text in _chunk_text(page_text, chunk_size, overlap):
            chunks.append(TextChunk(text=text, chunk_index=chunk_index, page=page_num))
            chunk_index += 1

    return chunks


def _load_docx(content: bytes, chunk_size: int, overlap: int) -> list[TextChunk]:
    """Load DOCX bytes and return chunks."""
    try:
        import docx
    except ImportError:
        raise RuntimeError("python-docx is required for DOCX support: pip install python-docx")

    doc = docx.Document(io.BytesIO(content))
    full_text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    return [
        TextChunk(text=t, chunk_index=i)
        for i, t in enumerate(_chunk_text(full_text, chunk_size, overlap))
    ]


def _load_csv(content: bytes, chunk_size: int, overlap: int) -> list[TextChunk]:
    """
    Parse CSV bytes, convert to Markdown table format so column headers are
    preserved with row data, and chunk logically for small LLMs.
    """
    text = content.decode("utf-8", errors="replace")
    reader = list(csv.reader(io.StringIO(text)))
    if not reader:
        return []

    header = [col.strip() for col in reader[0]]
    rows = reader[1:]

    if not header:
        return _load_text(content, chunk_size, overlap)

    header_str = "| " + " | ".join(header) + " |"
    separator_str = "| " + " | ".join(["---"] * len(header)) + " |"

    table_lines = [header_str, separator_str]
    for row in rows:
        row_vals = [col.strip() for col in row]
        row_padded = row_vals + [""] * (len(header) - len(row_vals))
        row_str = "| " + " | ".join(row_padded[: len(header)]) + " |"
        table_lines.append(row_str)

    full_table_text = "\n".join(table_lines)
    raw_chunks = _chunk_text(full_table_text, chunk_size, overlap)

    chunks: list[TextChunk] = []
    for i, t in enumerate(raw_chunks):
        if i > 0 and header_str not in t:
            chunk_text = f"{header_str}\n{separator_str}\n{t}"
        else:
            chunk_text = t
        chunks.append(TextChunk(text=chunk_text, chunk_index=i))

    return chunks


def _load_excel(content: bytes, chunk_size: int, overlap: int) -> list[TextChunk]:
    """
    Load Excel (.xlsx, .xls) bytes using openpyxl, convert sheets to Markdown tables,
    and return text chunks.
    """
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is required for Excel support: pip install openpyxl")

    wb = openpyxl.load_workbook(filename=io.BytesIO(content), data_only=True)
    all_sheet_texts = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        non_empty_rows = [
            r for r in rows if any(cell is not None and str(cell).strip() != "" for cell in r)
        ]
        if not non_empty_rows:
            continue

        header = [str(cell).strip() if cell is not None else "" for cell in non_empty_rows[0]]
        header_str = "| " + " | ".join(header) + " |"
        separator_str = "| " + " | ".join(["---"] * len(header)) + " |"

        table_lines = [f"### Sheet: {sheet_name}", header_str, separator_str]
        for row in non_empty_rows[1:]:
            row_vals = [str(cell).strip() if cell is not None else "" for cell in row]
            row_padded = row_vals + [""] * (len(header) - len(row_vals))
            table_lines.append("| " + " | ".join(row_padded[: len(header)]) + " |")

        sheet_table_text = "\n".join(table_lines)
        all_sheet_texts.append(sheet_table_text)

    full_excel_text = "\n\n---\n\n".join(all_sheet_texts)
    if not full_excel_text.strip():
        return []

    return [
        TextChunk(text=t, chunk_index=i)
        for i, t in enumerate(_chunk_text(full_excel_text, chunk_size, overlap))
    ]


def _load_text(content: bytes, chunk_size: int, overlap: int) -> list[TextChunk]:
    """Load plain text / markdown bytes and return chunks."""
    text = content.decode("utf-8", errors="replace")
    return [
        TextChunk(text=t, chunk_index=i)
        for i, t in enumerate(_chunk_text(text, chunk_size, overlap))
    ]


def load_and_chunk(
    content: bytes,
    filename: str,
    chunk_size: int = 600,
    overlap: int = 120,
) -> list[TextChunk]:
    """
    Main entry point: detect file type by extension and return text chunks.

    Args:
        content:    Raw file bytes.
        filename:   Original filename (used to detect type by extension).
        chunk_size: Target characters per chunk.
        overlap:    Characters to overlap between consecutive chunks.

    Returns:
        List of TextChunk objects.

    Raises:
        ValueError: If the file type is unsupported.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    logger.info("Loading '%s' (type: %s, size: %d bytes)", filename, ext, len(content))

    if ext == "pdf":
        chunks = _load_pdf(content, chunk_size, overlap)
    elif ext in ("docx", "doc"):
        chunks = _load_docx(content, chunk_size, overlap)
    elif ext in ("xlsx", "xls"):
        chunks = _load_excel(content, chunk_size, overlap)
    elif ext == "csv":
        chunks = _load_csv(content, chunk_size, overlap)
    elif ext in ("txt", "md", "rst"):
        chunks = _load_text(content, chunk_size, overlap)
    else:
        raise ValueError(
            f"Unsupported file type '.{ext}'. Supported: pdf, docx, xlsx, xls, csv, txt, md, rst"
        )

    logger.info("Created %d chunks from '%s'", len(chunks), filename)
    return chunks
