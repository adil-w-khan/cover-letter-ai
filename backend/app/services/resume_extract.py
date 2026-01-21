from io import BytesIO
from pypdf import PdfReader
import docx

MAX_EXTRACTED_CHARS = 20000  # cost control + prompt size control

def normalize_text(t: str) -> str:
    t = t.replace("\x00", " ")
    t = " ".join(t.split())
    return t.strip()

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(file_bytes))
    chunks = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        chunks.append(txt)
    text = normalize_text("\n".join(chunks))
    return text[:MAX_EXTRACTED_CHARS]

def extract_text_from_docx(file_bytes: bytes) -> str:
    f = BytesIO(file_bytes)
    document = docx.Document(f)
    chunks = [p.text for p in document.paragraphs if p.text]
    text = normalize_text("\n".join(chunks))
    return text[:MAX_EXTRACTED_CHARS]
