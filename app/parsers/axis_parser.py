import re
from typing import List, Dict

def parse_axis_statement(text: str) -> Dict:
    # Dummy regexes for demonstration; adjust for real statement formats
    account_holder = re.search(r"Account Holder\s*:\s*(.+)", text)
    account_number = re.search(r"Account Number\s*:\s*([Xx\d-]+)", text)

    # Transaction regex: date, description, amount, balance (very basic)
    transaction_pattern = re.compile(
        r"(\d{2,4}-\d{2}-\d{2})\s+([A-Z0-9 .,&'-]+)\s+([+-]?₹[\d,]+\.\d{2})\s+(₹[\d,]+\.\d{2})"
    )
    transactions: List[Dict] = []
    for match in transaction_pattern.finditer(text):
        transactions.append({
            "date": match.group(1),
            "description": match.group(2).strip(),
            "amount": match.group(3),
            "balance": match.group(4)
        })

    return {
        "account_holder": account_holder.group(1) if account_holder else "",
        "account_number": account_number.group(1) if account_number else "",
        "transactions": transactions
    } 