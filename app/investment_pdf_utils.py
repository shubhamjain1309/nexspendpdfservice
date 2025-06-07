import io
import re
import pikepdf
import pdfplumber
from datetime import datetime
from typing import List, Dict, Any

HOLDING_REGEX = re.compile(r"^([A-Z]{2}[0-9A-Z]{9}[0-9])\s+([A-Z &\-\.\(\)]+?)\s+([0-9,]+)\s+₹\s*([0-9,]+\.[0-9]{2})\s+₹\s*([0-9,]+\.[0-9]{2})", re.MULTILINE)

PORTFOLIO_VALUATION_YEAR_REGEX = re.compile(
    r"([A-Za-z]{3} \d{4})\s+([\d,]+\.\d{2})\s+([\-\d,]+\.\d{2})\s+([\-\d\.]+)"
)

PORTFOLIO_ACCOUNTS_MONTH_REGEX = re.compile(
    r"([A-Za-z ]+)\s+([\d,]+\.?\d*)\s+(\d+\.\d{2})"
)

# Step 1: Find blocks for each holding (ISIN, multiline security, then numbers)
HOLDING_EQUITY_BLOCK_REGEX = re.compile(
    r"([A-Z0-9]{12})\n([\s\S]+?)\n([\d\.]+)\s+--\s+--\s+--\s+([\d\.]+)\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)",
    re.MULTILINE
)


def _clean_number(num_str: str) -> float:
    try:
        # Remove commas and any trailing non-digit/period characters
        cleaned = re.sub(r'[^\d\.]', '', num_str.replace(',', ''))
        # Remove trailing periods (e.g., '1260.,' -> '1260.')
        cleaned = cleaned.rstrip('.')
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _parse_holdings(text: str) -> List[Dict[str, Any]]:
    holdings = []
    for match in HOLDING_REGEX.finditer(text):
        isin, name, quantity, price, value = match.groups()
        holdings.append({
            "isin": isin.strip(),
            "name": name.strip(),
            "quantity": _clean_number(quantity),
            "market_price": _clean_number(price),
            "market_value": _clean_number(value),
        })
    return holdings


def _parse_portfolio_valuation_year(text: str) -> List[Dict[str, Any]]:
    results = []
    for match in PORTFOLIO_VALUATION_YEAR_REGEX.finditer(text):
        month_year, value, change_amt, change_pct = match.groups()
        results.append({
            "month_year": month_year,
            "portfolio_value": float(value.replace(',', '')),
            "change_amount": float(change_amt.replace(',', '')),
            "change_percent": float(change_pct),
        })
    return results


def _parse_portfolio_accounts_month(text: str) -> List[Dict[str, Any]]:
    results = []
    seen = set()
    allowed_classes = {"equity", "mutual fund folios"}
    for match in PORTFOLIO_ACCOUNTS_MONTH_REGEX.finditer(text):
        asset_class, value, percent = match.groups()
        asset_class_clean = asset_class.strip().lower()
        value_num = float(value.replace(',', ''))
        percent_num = float(percent)
        key = (asset_class_clean, value_num, percent_num)
        if asset_class_clean in allowed_classes and key not in seen:
            results.append({
                "asset_class": asset_class.strip(),
                "value": value_num,
                "percentage": percent_num,
            })
            seen.add(key)
        # Stop if asset_class is 'total' and percentage is 100.00
        if asset_class_clean == 'total' and percent_num == 100.00:
            break
    return results


def _parse_holding_statement_equity(text: str) -> List[Dict[str, Any]]:
    results = []
    # Find all ISINs and their positions
    isin_regex = re.compile(r"([A-Z0-9]{12})")
    matches = list(isin_regex.finditer(text))
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        lines = block.splitlines()
        # ISIN is always first 12 characters of the first line
        first_line = lines[0].strip()
        isin = first_line[:12]
        # If there is more text after the ISIN on the first line, include it in the security name
        if len(first_line) > 12:
            security_lines = [first_line[12:].strip()] + [l.strip() for l in lines[1:-1]]
        else:
            security_lines = [l.strip() for l in lines[1:-1]]
        security = ' '.join(l for l in security_lines if l)
        # Find the line with numbers (should be the last line)
        number_line = lines[-1].strip()
        # Try to extract numbers from the last line
        num_match = re.search(r"([\d,.]+)\s+--\s+--\s+--\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)", number_line)
        if not num_match:
            # Try alternate pattern (for inline ISIN/security)
            num_match = re.search(r"([\d,.]+)\s+--\s+--\s+--\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)", block)
        if not num_match:
            continue  # skip if numbers not found
        current_bal, free_bal, market_price, value = num_match.groups()
        results.append({
            "isin": isin,
            "security": security,
            "current_balance": float(current_bal.replace(',', '')),
            "free_balance": float(free_bal.replace(',', '')),
            "market_price": float(market_price.replace(',', '')),
            "value": float(value.replace(',', '')),
        })
    return results

def _clean_number(s: str) -> float:
    """
    Remove commas and convert to float. If string is empty or invalid, returns 0.0.
    """
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

def _parse_mutual_fund_units_held(text: str) -> List[Dict[str, Any]]:
    """Parse the MUTUAL FUND UNITS HELD section. Handles multi-line scheme names and data rows."""
    results: List[Dict[str, Any]] = []
    lines = [l.strip() for l in text.splitlines()]
    # 1. Locate the section title
    title_idx = None
    for idx, line in enumerate(lines):
        if re.search(r"mutual fund units held", line, re.IGNORECASE):
            title_idx = idx
            break
    if title_idx is None:
        return results

    # 2. Stop at Grand Total or end
    end_idx = None
    for idx in range(title_idx + 1, len(lines)):
        if re.search(r"grand total", lines[idx], re.IGNORECASE):
            end_idx = idx
            break
    section_lines = lines[title_idx + 1:end_idx] if end_idx else lines[title_idx + 1:]

    isin_regex = re.compile(r"([A-Z]{2}[A-Z0-9]{9}[0-9])")
    buffer: List[str] = []  # Accumulate scheme name lines until we hit ISIN
    i = 0
    while i < len(section_lines):
        line = section_lines[i].strip()
        if not line:
            i += 1
            continue
        m = isin_regex.search(line)
        if m:
            isin = m.group(1)
            # Scheme name = buffered lines + part before ISIN on this line
            prefix_scheme = line[:m.start()].strip()
            scheme_name = ' '.join([*buffer, prefix_scheme]).strip()
            buffer = []  # reset for next record

            # Token collection for the current fund entry
            all_tokens_for_entry = []
            
            # Add tokens from the remainder of the current ISIN line
            remainder_on_isin_line = line[m.end():].strip()
            if remainder_on_isin_line:
                all_tokens_for_entry.extend(remainder_on_isin_line.split())

            # Look ahead one or two lines for more tokens, stop if new ISIN encountered
            lines_to_look_ahead = 2
            actual_lines_consumed_ahead = 0
            for k in range(lines_to_look_ahead):
                next_line_idx = i + 1 + k
                if next_line_idx < len(section_lines):
                    next_line_text = section_lines[next_line_idx]
                    next_isin_match = isin_regex.search(next_line_text)
                    # If next line starts with a *different* ISIN, it's a new record, so stop.
                    if next_isin_match and next_line_text.strip().startswith(next_isin_match.group(1)) and next_isin_match.group(1) != isin:
                        break
                    all_tokens_for_entry.extend(next_line_text.split())
                    actual_lines_consumed_ahead += 1
                else:
                    break # No more lines in section

            # Advance main loop counter 'i' by the number of extra lines consumed
            i += actual_lines_consumed_ahead

            # Now parse `all_tokens_for_entry`
            arn_idx = next((idx for idx, tok in enumerate(all_tokens_for_entry) if re.match(r"^(DIRECT|ARNDIRECT|ARN-?DIRECT|ARN\d+)$", tok, re.IGNORECASE)), None)
            
            if arn_idx is None:
                continue 

            folio_no = all_tokens_for_entry[arn_idx - 1] if arn_idx > 0 and arn_idx -1 < len(all_tokens_for_entry) else ""
            
            # Filter for numeric tokens *after* ARN
            numeric_tokens = [t for t in all_tokens_for_entry[arn_idx + 1:] if re.search(r"\d", t)]
            if len(numeric_tokens) < 4:
                i += 1
                continue
            closing_balance_units = numeric_tokens[0]
            # Handle NAV possibly split with trailing '-' sign
            nav_token = numeric_tokens[1]
            if nav_token.endswith('-') and len(numeric_tokens) >= 3:
                nav = nav_token.rstrip('-') + numeric_tokens[2]
                remainder_idx = 3
            else:
                nav = nav_token
                remainder_idx = 2
            if len(numeric_tokens) < remainder_idx + 2:
                i += 1
                continue
            cumulative_amount_invested = numeric_tokens[remainder_idx]
            valuation = numeric_tokens[remainder_idx + 1]
            # Validation: ensure numeric coherence
            cb_units_f = _clean_number(closing_balance_units)
            nav_f = _clean_number(nav)
            valuation_f = _clean_number(valuation)
            if cb_units_f == 0 or nav_f == 0 or valuation_f == 0:
                i += 1
                continue
            derived_nav = valuation_f / cb_units_f if cb_units_f else 0
            if nav_f == 0 or derived_nav == 0 or abs(derived_nav - nav_f) / nav_f > 0.3:
                i += 1
                continue
            results.append({
                "isin": isin,
                "folio_no": folio_no,
                "closing_balance_units": closing_balance_units,
                "nav": nav,
                "cumulative_amount_invested": cumulative_amount_invested,
                "valuation": valuation,
            })
        else:
            # No ISIN in this line; part of scheme name.
            if line and not re.search(r"scheme name", line, re.IGNORECASE):
                buffer.append(line)
        i += 1

    # If no results found, fallback to global scan based purely on mutual-fund ISIN prefix (INF)
    if not results:
        isin_regex_global = re.compile(r"\b(INF[A-Z0-9]{9}[0-9])\b")
        buffer = []
        for idx, line in enumerate(lines):
            # Skip lines that contain transaction statement keywords
            if any(keyword in line.lower() for keyword in [
                'transaction description', 'opening balance', 'closing balance', 
                'systematic investment', 'sip purchase', 'instalment no', 
                'purchase', 'redemption', 'dividend', 'nav (`)', 'price (`)', 
                'amount (`)', 'units', 'income capital stamp', 'date transaction',
                'folio no :', 'mode of holding', 'kyc of investor', 'nominee :'
            ]):
                continue
                
            m = isin_regex_global.search(line)
            if m:
                isin = m.group(1)
                # Scheme name from buffer + prefix before ISIN
                prefix = line[:m.start()].strip()
                scheme_name = ' '.join([*buffer, prefix]).strip()
                
                # Skip if scheme name contains transaction keywords
                if any(keyword in scheme_name.lower() for keyword in [
                    'transaction description', 'opening balance', 'closing balance',
                    'systematic investment', 'sip purchase', 'instalment no',
                    'income capital stamp', 'date transaction', 'summary of investments'
                ]):
                    buffer = []
                    continue
                
                buffer = []
                
                # Token collection for the current fund entry in fallback
                all_tokens_for_entry_fb = []
                remainder_on_isin_line_fb = line[m.end():].strip()
                if remainder_on_isin_line_fb:
                    all_tokens_for_entry_fb.extend(remainder_on_isin_line_fb.split())

                lines_to_look_ahead_fb = 2
                # Note: `idx` is from `enumerate(lines)`, `lines` is full PDF text lines
                for k_fb in range(lines_to_look_ahead_fb):
                    next_line_fb_pdf_idx = idx + 1 + k_fb # actual index in the full `lines` list
                    if next_line_fb_pdf_idx < len(lines):
                        next_line_text_fb = lines[next_line_fb_pdf_idx].strip()
                        # Skip if it's a transaction-like line based on keywords (already filtered for scheme name)
                        if any(keyword in next_line_text_fb.lower() for keyword in [
                            'transaction description', 'opening balance', 'closing balance', 'systematic investment', 
                            'sip purchase', 'instalment no', 'purchase', 'redemption', 'dividend', 
                            'folio no :', 'mode of holding', 'kyc of investor', 'nominee :'
                        ]): # More aggressive skip for lines after ISIN in fallback
                            continue # Skip this line, but allow loop to check next

                        next_isin_match_fb = isin_regex_global.search(next_line_text_fb)
                        if next_isin_match_fb and next_line_text_fb.strip().startswith(next_isin_match_fb.group(1)) and next_isin_match_fb.group(1) != isin:
                            break
                        all_tokens_for_entry_fb.extend(next_line_text_fb.split())
                        # Fallback doesn't need to manage outer loop's `idx` in the same way main parser does `i`
                    else:
                        break
                
                arn_idx_fb = next((pi for pi, tok in enumerate(all_tokens_for_entry_fb) if re.match(r"^(DIRECT|ARNDIRECT|ARN-?DIRECT|ARN\d+)$", tok, re.IGNORECASE)), None)
                if arn_idx_fb is None:
                    continue

                folio_no_fb = all_tokens_for_entry_fb[arn_idx_fb - 1] if arn_idx_fb > 0 and arn_idx_fb -1 < len(all_tokens_for_entry_fb) else ""
                
                numeric_tokens_fb = [t for t in all_tokens_for_entry_fb[arn_idx_fb + 1:] if re.search(r"\d", t)]
                if len(numeric_tokens_fb) < 4:
                    continue
                
                closing_balance_units = numeric_tokens_fb[0]
                # ... rest of fallback numeric parsing and validation ...
                nav_token_fb = numeric_tokens_fb[1]
                if nav_token_fb.endswith('-') and len(numeric_tokens_fb) >= 3:
                    nav = nav_token_fb.rstrip('-') + numeric_tokens_fb[2]
                    remainder_idx_fb = 3
                else:
                    nav = nav_token_fb
                    remainder_idx_fb = 2
                
                if len(numeric_tokens_fb) < remainder_idx_fb + 2:
                    continue
                cumulative_amount_invested = numeric_tokens_fb[remainder_idx_fb]
                valuation = numeric_tokens_fb[remainder_idx_fb + 1]
                # ... (validation logic as in main parser)
                cb_units_f = _clean_number(closing_balance_units)
                nav_f = _clean_number(nav)
                valuation_f = _clean_number(valuation)
                if cb_units_f == 0 or nav_f == 0 or valuation_f == 0: # Basic check
                    continue
                derived_nav = valuation_f / cb_units_f if cb_units_f else 0
                if nav_f == 0 or derived_nav == 0 or abs(derived_nav - nav_f) / nav_f > 0.3: # Coherence check
                    continue

                results.append({
                    "isin": isin,
                    "folio_no": folio_no_fb, # Use folio from fallback
                    "closing_balance_units": closing_balance_units,
                    "nav": nav,
                    "cumulative_amount_invested": cumulative_amount_invested,
                    "valuation": valuation,
                })
            else:
                if line and not re.search(r"scheme name", line, re.IGNORECASE):
                    buffer.append(line)

    return results

def process_investment_pdf(file_bytes: bytes, password: str, statement_type: str, institution: str) -> Dict[str, Any]:
    """Unlock the PDF, extract text, and parse holdings, transactions, and portfolio valuation tables."""
    try:
        # 1. Unlock PDF in-memory
        with pikepdf.open(io.BytesIO(file_bytes), password=password) as pdf:
            unlocked = io.BytesIO()
            pdf.save(unlocked)
            unlocked.seek(0)

        # 2. Extract text with pdfplumber (concatenate all pages)
        with pdfplumber.open(unlocked) as pdf:
            text = "\n".join(page.extract_text() or '' for page in pdf.pages)

        # Extract statement period (start and end date)
        period_regex = re.compile(r"Statement for the period from (\d{2}-[A-Za-z]{3}-\d{4}) to (\d{2}-[A-Za-z]{3}-\d{4})", re.IGNORECASE)
        period_match = period_regex.search(text)
        period_start_iso = None
        period_end_iso = None
        if period_match:
            period_start_str, period_end_str = period_match.groups()
            try:
                period_start_iso = datetime.strptime(period_start_str, "%d-%b-%Y").date().isoformat()
                period_end_iso = datetime.strptime(period_end_str, "%d-%b-%Y").date().isoformat()
            except Exception:
                period_start_iso = period_start_str
                period_end_iso = period_end_str

        # 3. Parse holdings
        holdings = _parse_holdings(text)

        # 4. Parse portfolio valuation for year
        portfolio_valuation_year = _parse_portfolio_valuation_year(text)
        for entry in portfolio_valuation_year:
            entry["period_start_date"] = period_start_iso
            entry["period_end_date"] = period_end_iso

        # 5. Parse portfolio accounts for month
        portfolio_accounts_month = _parse_portfolio_accounts_month(text)
        for entry in portfolio_accounts_month:
            entry["period_start_date"] = period_start_iso
            entry["period_end_date"] = period_end_iso

        # 6. Parse holding statement equity
        holding_statement_equity = _parse_holding_statement_equity(text)
        for entry in holding_statement_equity:
            entry["period_start_date"] = period_start_iso
            entry["period_end_date"] = period_end_iso

        # 7. Parse mutual fund units held
        mutual_fund_units_held = _parse_mutual_fund_units_held(text)
        for entry in mutual_fund_units_held:
            entry["period_start_date"] = period_start_iso
            entry["period_end_date"] = period_end_iso

        # TODO: implement transaction parsing using regex rules from spec
        transactions: List[Dict[str, Any]] = []

        return {
            "status": "success",
            "data": {
                "portfolio_valuation_year": portfolio_valuation_year,
                "portfolio_accounts_month": portfolio_accounts_month,
                "holding_statement_equity": holding_statement_equity,
                "mutual_fund_units_held": mutual_fund_units_held,
            },
        }
    except pikepdf.PasswordError:
        return {"status": "error", "message": "Invalid PDF password."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to parse PDF: {str(e)}"} 