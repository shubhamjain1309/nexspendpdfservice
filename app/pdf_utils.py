import io
import pikepdf
import pdfplumber
from app.parsers.axis_parser import parse_axis_statement
from app.parsers.hdfc_parser import parse_hdfc_statement

def detect_bank(text: str) -> str:
    text_lower = text.lower()
    if "axis bank" in text_lower:
        return "axis"
    elif "hdfc bank" in text_lower or "hdfc credit card" in text_lower:
        return "hdfc"
    else:
        return "unknown"

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

        # Detect bank and parse accordingly
        bank = detect_bank(text)
        if bank == "axis":
            data = parse_axis_statement(text)
        elif bank == "hdfc":
            data = parse_hdfc_statement(text)
        else:
            return {"status": "error", "message": "Bank not recognized or supported."}

        return {"status": "success", "data": data}
    except Exception:
        return {"status": "error", "message": "Unable to unlock or parse the PDF."} 