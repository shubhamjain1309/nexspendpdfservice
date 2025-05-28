import io
import pikepdf
import pdfplumber
from app.parsers.axis_parser import parse_axis_statement
from app.parsers.hdfc_parser import parse_hdfc_statement, parse_hdfc_account_statement
from datetime import datetime

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

def normalize_transactions(transactions, bank, document_type):
    normalized = []
    for txn in transactions:
        # Extract and normalize fields
        raw_type = (txn.get('type') or '').lower()
        if raw_type == 'credit':
            tx_type = 'income'
        elif raw_type == 'debit':
            tx_type = 'expenses'
        elif raw_type == 'savings':
            tx_type = 'savings'
        else:
            tx_type = 'expenses'
        # Date normalization (convert DD/MM/YYYY HH:MM:SS to ISO)
        raw_date = txn.get('date') or txn.get('timestamp') or ''
        timestamp = ''
        if raw_date:
            try:
                timestamp = datetime.strptime(raw_date, "%d/%m/%Y %H:%M:%S").isoformat(timespec='minutes')
            except Exception:
                timestamp = raw_date  # fallback to raw if parsing fails
        description = txn.get('description') or txn.get('narration') or ''
        amount = txn.get('amount') or ''
        # Truncate amount to two decimal places (as string, no rounding)
        try:
            amount_str = str(amount).replace(',', '')
            if '.' in amount_str:
                integer_part, decimal_part = amount_str.split('.', 1)
                decimal_part = decimal_part[:2]
                amount = integer_part + '.' + decimal_part
            else:
                amount = amount_str
        except Exception:
            pass  # leave as is if conversion fails
        category = txn.get('category') or ''
        if not category or category.strip().lower() in ('', 'unknown'):
            category = 'other' if tx_type != 'savings' else 'others'
        normalized.append({
            'timestamp': timestamp,
            'description': description,
            'amount': amount,
            'type': tx_type,
            'category': category
        })
    return normalized

# Parser registry: (bank, document_type) -> parser function
PARSER_REGISTRY = {
    ('hdfc', 'bank_statement'): parse_hdfc_statement,
    ('hdfc', 'credit_card_statement'): parse_hdfc_statement,  # Example, can be different
    ('hdfc', 'investment_statement'): None,  # Not implemented
    ('hdfc_account', 'bank_statement'): parse_hdfc_account_statement,
    ('axis', 'bank_statement'): parse_axis_statement,
    # Add more as needed
}

def process_pdf(file_bytes: bytes, password: str, bank: str, document_type: str) -> dict:
    try:
        # Unlock PDF in memory
        with pikepdf.open(io.BytesIO(file_bytes), password=password) as pdf:
            unlocked_pdf = io.BytesIO()
            pdf.save(unlocked_pdf)
            unlocked_pdf.seek(0)

        # Extract text with pdfplumber
        with pdfplumber.open(unlocked_pdf) as pdf:
            text = "\n".join(page.extract_text() or '' for page in pdf.pages)
            print("Extracted text:\n", text[:500])  # Print first 500 chars for debug

        # Use provided bank and document_type for parser routing
        key = (bank, document_type)
        parser = PARSER_REGISTRY.get(key)
        if not parser:
            # Try fallback for hdfc_account
            if bank == 'hdfc_account':
                parser = PARSER_REGISTRY.get(('hdfc_account', document_type))
            if not parser:
                print(f"No parser for bank '{bank}' and document type '{document_type}'")
                return {"status": "error", "message": f"No parser for bank '{bank}' and document type '{document_type}'."}
        data = parser(text)
        print("RAW parser output:", data)
        transactions = data.get('transactions', [])
        normalized = normalize_transactions(transactions, bank, document_type)
        print("Normalized output:", normalized)
        return {"status": "success", "data": {"transactions": normalized}}
    except Exception as e:
        print(f"Exception in process_pdf: {e}")
        return {"status": "error", "message": f"Unable to unlock or parse the PDF: {str(e)}"} 