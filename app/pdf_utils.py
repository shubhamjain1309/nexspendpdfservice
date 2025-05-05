import io
import pikepdf
import pdfplumber
from app.parsers.axis_parser import parse_axis_statement

def process_pdf(file_bytes: bytes, password: str) -> dict:
    try:
        # Unlock PDF in memory
        with pikepdf.open(io.BytesIO(file_bytes), password=password) as pdf:
            unlocked_pdf = io.BytesIO()
            pdf.save(unlocked_pdf)
            unlocked_pdf.seek(0)

        # Extract text with pdfplumber
        with pdfplumber.open(unlocked_pdf) as pdf:
            text = "\n".join(page.extract_text() or '' for page in pdf.pages)

        # Basic parser (replace with bank-specific as needed)
        data = parse_axis_statement(text)
        return {"status": "success", "data": data}
    except Exception:
        return {"status": "error", "message": "Unable to unlock or parse the PDF."} 