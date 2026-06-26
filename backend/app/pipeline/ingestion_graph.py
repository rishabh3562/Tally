"""LangGraph-based ingestion pipeline with AI agents."""

import logging
from typing import TypedDict, Any
from datetime import datetime
from uuid import uuid4
from supabase import Client

from app.core.openrouter_manager import OpenRouterClient
from app.services.parser import parse_pdf, parse_csv, parse_xlsx
from app.services.deduplicator import fingerprint, filter_duplicates
from app.services.merchant import normalize_merchant
from app.services.categorizer import categorize_transaction, get_category_id

logger = logging.getLogger(__name__)


class IngestionState(TypedDict):
    """State for ingestion workflow."""

    job_id: str
    user_id: str
    account_id: str
    file_bytes: bytes
    file_ext: str
    bank_code: str
    db: Client
    llm_client: OpenRouterClient
    # Pipeline results
    raw_transactions: list
    parsed_count: int
    deduped_transactions: list
    duplicates_skipped: int
    normalized_transactions: list
    categorized_transactions: list
    inserted_count: int
    errors: list
    status: str


class IngestionAgent:
    """Multi-step ingestion agent using LangGraph."""

    def __init__(self, llm_client: OpenRouterClient = None):
        """Initialize agent with LLM client."""
        self.llm_client = llm_client or OpenRouterClient()

    async def parse_statement(self, state: IngestionState) -> IngestionState:
        """Parse bank statement file."""
        try:
            logger.info(f"Parsing {state['file_ext']} for {state['bank_code']}")

            if state["file_ext"].lower() == "pdf":
                raw_txs = parse_pdf(state["file_bytes"], state["bank_code"])
            elif state["file_ext"].lower() == "csv":
                raw_txs = parse_csv(state["file_bytes"], state["bank_code"])
            elif state["file_ext"].lower() in ["xlsx", "xls"]:
                raw_txs = parse_xlsx(state["file_bytes"], state["bank_code"])
            else:
                raise ValueError(f"Unsupported: {state['file_ext']}")

            if not raw_txs:
                raise ValueError("No transactions found")

            state["raw_transactions"] = raw_txs
            state["parsed_count"] = len(raw_txs)
            logger.info(f"Parsed {len(raw_txs)} transactions")
        except Exception as e:
            logger.error(f"Parse failed: {e}")
            state["errors"].append({"step": "parse", "error": str(e)})
            state["status"] = "failed"

        return state

    async def deduplicate(self, state: IngestionState) -> IngestionState:
        """Deduplicate transactions."""
        try:
            db = state["db"]
            existing_fps = set()

            try:
                resp = db.table("transactions").select("fingerprint").eq(
                    "account_id", state["account_id"]
                ).execute()
                existing_fps = {row["fingerprint"] for row in (resp.data or [])}
            except Exception as e:
                logger.warning(f"Could not fetch existing fingerprints: {e}")

            new_txs, skipped = filter_duplicates(
                state["raw_transactions"],
                existing_fps,
                state["account_id"],
            )

            state["deduped_transactions"] = new_txs
            state["duplicates_skipped"] = len(skipped)
            logger.info(f"Dedup: {len(new_txs)} new, {len(skipped)} skipped")

        except Exception as e:
            logger.error(f"Dedup failed: {e}")
            state["errors"].append({"step": "deduplicate", "error": str(e)})
            state["status"] = "failed"

        return state

    async def normalize_merchants(self, state: IngestionState) -> IngestionState:
        """Normalize merchant names."""
        try:
            logger.info("Normalizing merchants")
            for tx in state["deduped_transactions"]:
                normalized = await normalize_merchant(tx["raw_merchant"], state["db"])
                tx["normalized_merchant"] = normalized

            state["normalized_transactions"] = state["deduped_transactions"]
            logger.info(f"Normalized {len(state['deduped_transactions'])} merchants")

        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            state["errors"].append({"step": "normalize", "error": str(e)})
            state["status"] = "failed"

        return state

    async def categorize(self, state: IngestionState) -> IngestionState:
        """Categorize transactions with AI agent fallback."""
        try:
            logger.info("Categorizing transactions")

            for tx in state["normalized_transactions"]:
                category, confidence = await categorize_transaction(
                    tx["normalized_merchant"],
                    tx["amount"],
                    tx.get("memo"),
                    state["db"],
                )

                # If low confidence, use AI agent for second opinion
                if confidence < 0.6:
                    try:
                        ai_category = await self._get_ai_category(
                            tx, state["llm_client"]
                        )
                        if ai_category:
                            category = ai_category
                            confidence = 0.75
                    except Exception as e:
                        logger.warning(f"AI categorization failed: {e}")

                tx["category_name"] = category
                tx["confidence_score"] = confidence

            state["categorized_transactions"] = state["normalized_transactions"]
            logger.info(
                f"Categorized {len(state['normalized_transactions'])} transactions"
            )

        except Exception as e:
            logger.error(f"Categorization failed: {e}")
            state["errors"].append({"step": "categorize", "error": str(e)})
            state["status"] = "failed"

        return state

    async def _get_ai_category(self, tx: dict, llm_client: OpenRouterClient) -> str:
        """Use AI to suggest category for ambiguous transaction."""
        try:
            response = await llm_client.call_llm(
                model="google/gemini-2.0-flash-exp",
                messages=[
                    {
                        "role": "user",
                        "content": f"""Categorize this transaction into ONE of: Food, Transport, Entertainment, Shopping, Utilities, Healthcare, Education, Travel, Groceries, Subscriptions, Other.

Merchant: {tx.get('normalized_merchant', 'Unknown')}
Amount: ₹{tx.get('amount', 0)}
Memo: {tx.get('memo', '')}

Respond with ONLY the category name, nothing else.""",
                    }
                ],
                max_tokens=20,
                temperature=0.3,
            )

            return response["content"].strip()
        except Exception as e:
            logger.warning(f"AI category suggestion failed: {e}")
            return None

    async def insert_transactions(self, state: IngestionState) -> IngestionState:
        """Insert categorized transactions into database."""
        try:
            logger.info(f"Inserting {len(state['categorized_transactions'])} transactions")

            for tx in state["categorized_transactions"]:
                try:
                    category_id = await get_category_id(
                        tx["category_name"],
                        state["user_id"],
                        state["db"],
                    )

                    insert_data = {
                        "user_id": state["user_id"],
                        "account_id": state["account_id"],
                        "date": tx["date"].isoformat(),
                        "amount": tx["amount"],
                        "currency": tx["currency"],
                        "raw_merchant": tx["raw_merchant"],
                        "category_id": category_id,
                        "memo": tx.get("memo", ""),
                        "fingerprint": tx["fingerprint"],
                        "confidence_score": tx["confidence_score"],
                        "is_transfer": False,
                    }

                    resp = state["db"].table("transactions").insert(insert_data).execute()
                    if resp.data:
                        state["inserted_count"] += 1

                except Exception as e:
                    logger.error(f"Insert failed for tx: {e}")
                    continue

            logger.info(f"Inserted {state['inserted_count']} transactions")
            state["status"] = "done"

        except Exception as e:
            logger.error(f"Insert step failed: {e}")
            state["errors"].append({"step": "insert", "error": str(e)})
            state["status"] = "failed"

        return state

    async def run(self, initial_state: IngestionState) -> IngestionState:
        """Run complete ingestion pipeline."""
        state = initial_state.copy()
        state["raw_transactions"] = []
        state["deduped_transactions"] = []
        state["normalized_transactions"] = []
        state["categorized_transactions"] = []
        state["inserted_count"] = 0
        state["errors"] = []
        state["status"] = "processing"

        # Sequential pipeline stages
        state = await self.parse_statement(state)
        if state["status"] == "failed":
            return state

        state = await self.deduplicate(state)
        if state["status"] == "failed":
            return state

        state = await self.normalize_merchants(state)
        if state["status"] == "failed":
            return state

        state = await self.categorize(state)
        if state["status"] == "failed":
            return state

        state = await self.insert_transactions(state)

        return state
