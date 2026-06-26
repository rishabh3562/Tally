"""Transaction deduplication service."""

import hashlib
from datetime import date
from typing import List, Dict, Any, Tuple


def fingerprint(
    date: date,
    amount: float,
    raw_merchant: str,
    account_id: str,
) -> str:
    """
    Create a deterministic fingerprint for a transaction.

    Args:
        date: Transaction date
        amount: Transaction amount
        raw_merchant: Raw merchant string
        account_id: Account UUID

    Returns:
        SHA256 hex digest
    """
    data = f"{date}|{amount}|{raw_merchant}|{account_id}"
    return hashlib.sha256(data.encode()).hexdigest()


def filter_duplicates(
    transactions: List[Dict[str, Any]],
    existing_fingerprints: set[str],
    account_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filter out duplicate transactions based on fingerprints.

    Args:
        transactions: New transactions to check
        existing_fingerprints: Set of already-stored fingerprints
        account_id: Account UUID

    Returns:
        Tuple of (new_transactions, skipped_transactions)
    """
    new = []
    skipped = []

    for tx in transactions:
        fp = fingerprint(
            tx["date"],
            tx["amount"],
            tx["raw_merchant"],
            account_id,
        )

        if fp in existing_fingerprints:
            skipped.append({"transaction": tx, "reason": "duplicate", "fingerprint": fp})
        else:
            tx["fingerprint"] = fp
            new.append(tx)

    return new, skipped
