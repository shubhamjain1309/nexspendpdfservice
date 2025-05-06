import io
import pikepdf
import pdfplumber
from app.parsers.axis_parser import parse_axis_statement
from app.parsers.hdfc_parser import parse_hdfc_statement, parse_hdfc_account_statement

def detect_bank(text: str) -> str:
    # Normalize text for robust matching
    text_norm = ' '.join(text.lower().split())
    # Check for HDFC Bank (account or credit card)
    if "hdfc bank" in text_norm or "we understand your world" in text_norm or "hdfc" in text_norm:
        if "withdrawal amt." in text_norm or "deposit amt." in text_norm:
            return "hdfc_account"
        else:
            return "hdfc"
    # Add more banks as needed
    elif "axis bank" in text_norm:
        return "axis"
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
            print(text)

        # Detect bank and parse accordingly
        bank = detect_bank(text)
        if bank == "axis":
            data = parse_axis_statement(text)
        elif bank == "hdfc":
            data = parse_hdfc_statement(text)
        elif bank == "hdfc_account":
            data = parse_hdfc_account_statement(text)
        else:
            return {"status": "error", "message": "Bank not recognized or supported."}

        return {"status": "success", "data": data}
    except Exception:
        return {"status": "error", "message": "Unable to unlock or parse the PDF."} 