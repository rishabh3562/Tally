"""File parsing service for bank statements."""

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


def parse_pdf(file_bytes: bytes, bank_code: str = "HDFC") -> List[Dict[str, Any]]:
    """
    Parse transactions from a PDF statement.

    Args:
        file_bytes: PDF file contents
        bank_code: Bank identifier (HDFC, ICICI, SBI, etc.)

    Returns:
        List of transaction dictionaries with keys:
        {date, amount, raw_merchant, memo, currency}
    """
    transactions = []

    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
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
