import re
from typing import List, Dict

def parse_hdfc_statement(text: str) -> Dict:
    transaction_pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})\s+(.+?)\s+([\d,]+\.\d{2})(?:\s*(Cr))?"
    )
    transactions: List[Dict] = []
    for match in transaction_pattern.finditer(text):
        amount = match.group(3)
        credit_debit = "credit" if match.group(4) else "debit"
        transactions.append({
            "date": match.group(1),
            "description": match.group(2).strip(),
            "amount": amount,
            "type": credit_debit
        })

    return {
        "transactions": transactions
    } 