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

def parse_hdfc_account_statement(text: str) -> dict:
    import re
    # List of patterns/keywords to ignore
    ignore_patterns = [
        r"^statement of account",
        r"^from\s*:", r"^to\s*:", r"^account no\s*:", r"^nomination\s*:",
        r"^joint holders", r"^page no", r"^hdfc bank", r"^we understand your world",
        r"^mr\. ", r"^address\s*:", r"^city\s*:", r"^state\s*:", r"^phone no\s*:",
        r"^od limit", r"^currency", r"^email", r"^cust id", r"^a/c open date",
        r"^account status", r"^rtgs/neft ifsc", r"^micr", r"^branch code", r"^product code",
        r"^registered office address", r"^the address on this statement", r"^contents of this statement",
        r"^state account branch gstn", r"^hdfc bank gstin number details", r"^club-cred"
    ]
    ignore_regex = re.compile("|".join(ignore_patterns), re.IGNORECASE)

    # Filter lines
    lines = [line.strip() for line in text.splitlines() if line.strip() and not ignore_regex.match(line.strip())]
    transactions = []
    buffer = []
    date_pattern = re.compile(r"^\d{2}/\d{2}/\d{2}")

    for line in lines:
        if date_pattern.match(line):
            if buffer:
                transactions.append(buffer)
                buffer = []
            buffer.append(line)
        else:
            # Only append to buffer if not a header/footer/meta line
            if buffer and not ignore_regex.match(line):
                buffer.append(line)
    if buffer:
        transactions.append(buffer)

    parsed = []
    prev_balance = None
    for idx, txn_lines in enumerate(transactions):
        first_line = txn_lines[0]
        narration_cont = " ".join(txn_lines[1:]).strip() if len(txn_lines) > 1 else ""
        match = re.match(
            r"^(\d{2}/\d{2}/\d{2})\s+(.+?)\s+(\d+)\s+(\d{2}/\d{2}/\d{2})\s*([0-9,]*\.?\d*)?\s*([0-9,]*\.?\d*)?\s+([0-9,]+\.\d{2})$",
            first_line
        )
        if match:
            date = match.group(1)
            narration = match.group(2)
            if narration_cont:
                narration += " " + narration_cont
            # Remove unwanted meta/footer phrases from narration
            unwanted_phrases = [
                "HDFCBANKLIMITED *Closingbalanceincludesfundsearmarkedforholdandunclearedfunds",
                "Contentsofthisstatementwillbeconsideredcorrectifnoerrorisreportedwithin30daysofreceiptofstatement.",
                "TheaddressonthisstatementisthatonrecordwiththeBankasatthedayofrequesting thisstatement.",
                "StateaccountbranchGSTN:24AAACH2702H1Z6",
                "HDFCBankGSTINnumberdetailsareavailableathttps://www.hdfcbank.com/personal/making-payments/online-tax-payment/goods-and-service-tax.",
                "RegisteredOfficeAddress:HDFCBankHouse,SenapatiBapatMarg,LowerParel,Mumbai400013",
                "PageNo.:",
                "AccountBranch :",
                "Phoneno. :",
                "VIPROADNEARMARIGOLDCIRCLE",
                "ODLimit :",
                "SOUTHBOPALBOPAL",
                "AHMEDABAD380058",
                "CustID :",
                "GUJARATINDIA",
                "AccountNo :",
                "A/COpenDate :",
                "JOINTHOLDERS:",
                "AccountStatus :",
                "RTGS/NEFTIFSC:",
                "MICR:",
                "BranchCode :",
                "ProductCode:",
                "STATEMENTSUMMARY :- OpeningBalance DrCount CrCount Debits Credits ClosingBal",
                "GeneratedOn:",
                "GeneratedBy:",
                "RequestingBranchCode:",
                "Thisisacomputergeneratedstatementanddoes notrequiresignature.",
                # Additional address, branch, and code fragments
                "SANANDBRANCH",
                "AAKARCOMPLEX,ABOVESBIBANK",
                "AHMEDABAD-SANANDHIGHWAY",
                "D-703,SAANVINIRMANESTELLA",
                "18002600/18001600",
                "0.00",
                "58655136",
                "50100072568832",
                "NEWDEEMEDHNWRBB",
                "31/01/2015",
                "Regular",
                "HDFC0001677",
                "380240034",
                "1677",
                "100"
            ]
            for phrase in unwanted_phrases:
                narration = narration.replace(phrase, "")
            # Remove standalone numbers of 6+ digits (likely account numbers, codes, etc.)
            narration = re.sub(r'\b\d{6,}\b', '', narration)
            withdrawal = match.group(5).replace(",", "") if match.group(5) else ""
            deposit = match.group(6).replace(",", "") if match.group(6) else ""
            balance = match.group(7).replace(",", "") if match.group(7) else None
            tx_type = "unknown"
            amount = ""
            # Use closing balance delta for all except the first transaction
            if prev_balance is not None and balance:
                try:
                    prev_bal = float(prev_balance)
                    curr_bal = float(balance)
                    if curr_bal > prev_bal:
                        tx_type = "credit"
                        amount = str(abs(curr_bal - prev_bal))
                    elif curr_bal < prev_bal:
                        tx_type = "debit"
                        amount = str(abs(curr_bal - prev_bal))
                    else:
                        tx_type = "unknown"
                        amount = ""
                except Exception:
                    # Fallback to column-based logic if conversion fails
                    if withdrawal and withdrawal != "":
                        amount = withdrawal
                        tx_type = "debit"
                    elif deposit and deposit != "":
                        amount = deposit
                        tx_type = "credit"
            else:
                # First transaction or missing balance, fallback to column-based logic
                if withdrawal and withdrawal != "":
                    amount = withdrawal
                    tx_type = "debit"
                elif deposit and deposit != "":
                    amount = deposit
                    tx_type = "credit"
            prev_balance = balance
            parsed.append({
                "date": date,
                "narration": narration.strip(),
                "amount": amount,
                "type": tx_type
            })
    return {"transactions": parsed} 