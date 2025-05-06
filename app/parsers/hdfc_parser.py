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

def parse_hdfc_account_statement(text: str) -> Dict:
    pattern = re.compile(
        r"(\d{2}/\d{2}/\d{2})\s+(.+?)\s+(\d+)\s+(\d{2}/\d{2}/\d{2})\s+([\d,]+\.\d{2})?\s*([\d,]+\.\d{2})?\s+([\d,]+\.\d{2})"
    )
    transactions: List[Dict] = []
    for match in pattern.finditer(text):
        date = match.group(1)
        narration = match.group(2).replace('\n', ' ').strip()
        ref_no = match.group(3)
        value_date = match.group(4)
        withdrawal = match.group(5)
        deposit = match.group(6)
        balance = match.group(7)
        if withdrawal:
            amount = withdrawal
            tx_type = "debit"
        elif deposit:
            amount = deposit
            tx_type = "credit"
        else:
            amount = ""
            tx_type = "unknown"
        transactions.append({
            "date": date,
            "narration": narration,
            "ref_no": ref_no,
            "value_date": value_date,
            "amount": amount,
            "type": tx_type,
            "balance": balance
        })
    return {"transactions": transactions} 