"""File parsing service for bank statements."""

import re
from io import BytesIO
from datetime import datetime
import pandas as pd
import pdfplumber
from typing import List, Dict, Any


# Bank-specific column mappings
BANK_PARSERS = {
    "HDFC": {
        "date_column": "Txn Date",
        "amount_column": "Debit Amount",
        "merchant_column": "Description",
        "memo_column": "Description",
        "skip_rows": 0,
    },
    "ICICI": {
        "date_column": "Transaction Date",
        "amount_column": "Amount",
        "merchant_column": "Narration",
        "memo_column": "Narration",
        "skip_rows": 0,
    },
    "SBI": {
        "date_column": "Date",
        "amount_column": "Debit",
        "merchant_column": "Description",
        "memo_column": "Description",
        "skip_rows": 0,
    },
    "AXIS": {
        "date_column": "Transaction Date",
        "amount_column": "Debit Amount",
        "merchant_column": "Transaction Details",
        "memo_column": "Transaction Details",
        "skip_rows": 0,
    },
    "KOTAK": {
        "date_column": "Date",
        "amount_column": "Withdrawal Amt.",
        "merchant_column": "Narration",
        "memo_column": "Narration",
        "skip_rows": 0,
    },
}


# --- Google Pay (UPI) statement parsing --------------------------------------
# GPay statements are text (not tables): each transaction spans a few lines,
#   07Dec,2025 PaidtoSwiggy ₹158
#   11:39AM UPITransactionID:534166108951
#   PaidbyStateBankofIndia9112
# pdfplumber strips most spaces, so the regexes tolerate the "no space" form.
_GPAY_HEADER = re.compile(
    r'^(\d{1,2}[A-Za-z]{3},\d{4})\s+(Paid ?to|Received ?from)\s*(.+?)\s*₹\s*([\d,]+(?:\.\d+)?)$'
)
_GPAY_TXN_ID = re.compile(r'UPI\s*Transaction\s*ID[:\s]*(\d+)', re.IGNORECASE)
_GPAY_FUNDING = re.compile(r'Paid ?(?:by|to)\s*(.+)', re.IGNORECASE)
_GPAY_TIME = re.compile(r'(\d{1,2}):(\d{2})\s*([AP]M)', re.IGNORECASE)


def looks_like_gpay(text: str) -> bool:
    """Heuristic: does this PDF text look like a Google Pay statement?"""
    compact = text.replace(" ", "").lower()
    return (
        "googlepay" in compact
        or "upitransactionid" in compact
        or ("transactionstatement" in compact and "upi" in compact)
    )


def parse_gpay_text(text: str) -> List[Dict[str, Any]]:
    """Parse Google Pay statement text into transactions.

    Money out ("Paid to") is stored as a positive amount (an expense); money in
    ("Received from") is stored negative, matching the app's spending-sum
    convention. Direction, UPI transaction id, time-of-day and funding source are
    now returned as first-class fields (and still summarised in the memo for
    human display).
    """
    lines = text.split("\n")
    transactions: List[Dict[str, Any]] = []

    for i, raw_line in enumerate(lines):
        m = _GPAY_HEADER.match(raw_line.strip())
        if not m:
            continue

        date_str, direction, merchant, amount_str = m.groups()
        try:
            date_obj = datetime.strptime(date_str, "%d%b,%Y").date()
        except ValueError:
            continue

        try:
            amount = float(amount_str.replace(",", ""))
        except ValueError:
            continue

        is_credit = direction.replace(" ", "").lower() == "receivedfrom"

        # Look ahead a couple of lines for the UPI id, time and funding source.
        txn_id = None
        funding = None
        txn_time = None
        for j in (i + 1, i + 2):
            if j < len(lines):
                if not txn_id:
                    tid = _GPAY_TXN_ID.search(lines[j])
                    if tid:
                        txn_id = tid.group(1)
                if not txn_time:
                    tm = _GPAY_TIME.search(lines[j])
                    if tm:
                        txn_time = _to_24h(tm.group(1), tm.group(2), tm.group(3))
                if "Paidby" in lines[j].replace(" ", ""):
                    funding = lines[j].strip()

        merchant = merchant.strip()
        direction_label = "credit" if is_credit else "debit"
        memo_parts = ["Received from" if is_credit else "Paid to", merchant]
        if txn_id:
            memo_parts.append(f"UPI:{txn_id}")
        if funding:
            memo_parts.append(funding)

        transactions.append({
            "date": date_obj,
            "amount": -amount if is_credit else amount,
            "raw_merchant": merchant,
            "counterparty": merchant,
            "memo": " | ".join(memo_parts),
            "currency": "INR",
            "direction": direction_label,
            "upi_transaction_id": txn_id,
            "txn_time": txn_time,
            "funding_source": funding,
        })

    return transactions


def _to_24h(hour: str, minute: str, meridiem: str) -> str:
    """Convert '11', '39', 'PM' -> '23:39:00' (a Postgres TIME literal)."""
    h = int(hour) % 12
    if meridiem.upper() == "PM":
        h += 12
    return f"{h:02d}:{int(minute):02d}:00"


def parse_pdf(file_bytes: bytes, bank_code: str = "HDFC") -> List[Dict[str, Any]]:
    """
    Parse transactions from a PDF statement.

    Auto-detects Google Pay/UPI statements (which are line-based text, not
    tables) and routes them to the GPay parser; otherwise falls back to the
    table-based bank parser selected by ``bank_code``.

    Returns:
        List of transaction dictionaries with keys:
        {date, amount, raw_merchant, memo, currency}
    """
    transactions = []

    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            full_text = "\n".join((page.extract_text() or "") for page in pdf.pages)

            if looks_like_gpay(full_text):
                return parse_gpay_text(full_text)

            for page in pdf.pages:
                # Try to extract table from page
                tables = page.extract_tables()
                if not tables:
                    continue

                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    # Use first row as header
                    headers = table[0]
                    for row in table[1:]:
                        try:
                            tx = _parse_row(row, headers, bank_code)
                            if tx:
                                transactions.append(tx)
                        except Exception:
                            continue

    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")

    return transactions


def parse_csv(file_bytes: bytes, bank_code: str = "HDFC") -> List[Dict[str, Any]]:
    """
    Parse transactions from a CSV statement.

    Args:
        file_bytes: CSV file contents
        bank_code: Bank identifier

    Returns:
        List of transaction dictionaries
    """
    try:
        df = pd.read_csv(BytesIO(file_bytes))
        transactions = []

        for _, row in df.iterrows():
            try:
                tx = _parse_row(row.to_list(), row.index.to_list(), bank_code)
                if tx:
                    transactions.append(tx)
            except Exception:
                continue

        return transactions
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {str(e)}")


def parse_xlsx(file_bytes: bytes, bank_code: str = "HDFC") -> List[Dict[str, Any]]:
    """
    Parse transactions from an Excel statement.

    Args:
        file_bytes: Excel file contents
        bank_code: Bank identifier

    Returns:
        List of transaction dictionaries
    """
    try:
        df = pd.read_excel(BytesIO(file_bytes))
        transactions = []

        for _, row in df.iterrows():
            try:
                tx = _parse_row(row.to_list(), row.index.to_list(), bank_code)
                if tx:
                    transactions.append(tx)
            except Exception:
                continue

        return transactions
    except Exception as e:
        raise ValueError(f"Failed to parse Excel: {str(e)}")


def _parse_row(
    row: List[Any], headers: List[str], bank_code: str
) -> Dict[str, Any] | None:
    """
    Parse a single transaction row.

    Args:
        row: List of values from the row
        headers: List of header column names
        bank_code: Bank identifier

    Returns:
        Transaction dict or None if parsing fails
    """
    parser_config = BANK_PARSERS.get(bank_code.upper())
    if not parser_config:
        return None

    try:
        # Create a simple dict from headers and row values
        row_dict = dict(zip(headers, row))

        date_str = row_dict.get(parser_config["date_column"], "").strip()
        amount_str = row_dict.get(parser_config["amount_column"], "").strip()
        merchant_str = row_dict.get(parser_config["merchant_column"], "").strip()
        memo_str = row_dict.get(parser_config["memo_column"], "").strip()

        if not all([date_str, amount_str, merchant_str]):
            return None

        # Parse date (try multiple formats)
        date_obj = None
        for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d"]:
            try:
                date_obj = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue

        if not date_obj:
            return None

        # Parse amount (handle INR currency)
        amount = float(amount_str.replace(",", "").replace("₹", "").strip())

        return {
            "date": date_obj,
            "amount": amount,
            "raw_merchant": merchant_str,
            "memo": memo_str or merchant_str,
            "currency": "INR",
        }

    except Exception:
        return None
