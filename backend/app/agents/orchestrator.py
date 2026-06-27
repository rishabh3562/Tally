"""Orchestrator agent that coordinates the financial processing workflow."""

import logging
from typing import Any, Dict
from app.agents.base import LLMConfig, AgentResult
from app.agents.parsing_agent import ParsingAgent, ValidationAgent
from app.agents.categorization_agent import (
    MerchantNormalizationAgent,
    CategorizationAgent,
)

logger = logging.getLogger(__name__)


class FinancialProcessingOrchestrator:
    """Orchestrates the full transaction processing workflow."""

    def __init__(self, llm_config: LLMConfig):
        self.llm = llm_config
        self.parsing_agent = ParsingAgent(llm_config)
        self.validation_agent = ValidationAgent(llm_config)
        self.merchant_agent = MerchantNormalizationAgent(llm_config)
        self.categorization_agent = CategorizationAgent(llm_config)

    async def process_statement(
        self,
        raw_transactions: list,
        bank_code: str,
        file_type: str,
    ) -> Dict[str, Any]:
        """
        Process a bank statement through the full pipeline.

        Returns:
            {
                "success": bool,
                "parsed_count": int,
                "valid_count": int,
                "transactions": [...],
                "errors": [...]
            }
        """
        logger.info(
            f"Starting statement processing: {len(raw_transactions)} transactions"
        )
        errors = []

        try:
            # Step 1: Parse
            logger.info("Step 1: Parsing transactions...")
            parse_result = await self.parsing_agent.run({
                "raw_transactions": raw_transactions,
                "bank_code": bank_code,
                "file_type": file_type,
            })

            if not parse_result.success:
                return {
                    "success": False,
                    "error": parse_result.error,
                    "parsed_count": 0,
                }

            parsed_txs = parse_result.data.get("transactions", [])
            logger.info(f"Parsed {len(parsed_txs)} transactions")

            # Step 2: Validate
            logger.info("Step 2: Validating transactions...")
            validation_result = await self.validation_agent.run({
                "transactions": parsed_txs,
            })

            if not validation_result.success:
                errors.append(validation_result.error)

            valid_txs = validation_result.data.get("valid_transactions", parsed_txs)
            logger.info(f"Validated {len(valid_txs)} transactions")

            # Step 3: Normalize Merchants
            logger.info("Step 3: Normalizing merchants...")
            normalization_result = await self.merchant_agent.run({
                "transactions": valid_txs,
            })

            if not normalization_result.success:
                errors.append(normalization_result.error)
                normalized_txs = valid_txs
            else:
                normalized_txs = normalization_result.data.get(
                    "normalized_transactions", valid_txs
                )

            logger.info(f"Normalized {len(normalized_txs)} merchants")

            # Step 4: Categorize
            logger.info("Step 4: Categorizing transactions...")
            categorization_result = await self.categorization_agent.run({
                "transactions": normalized_txs,
            })

            if not categorization_result.success:
                errors.append(categorization_result.error)
                categorized_txs = normalized_txs
            else:
                categorized_txs = categorization_result.data.get(
                    "categorized_transactions", normalized_txs
                )

            category_dist = categorization_result.data.get("category_distribution", {})
            logger.info(f"Categorized {len(categorized_txs)} transactions")
            logger.info(f"Category distribution: {category_dist}")

            # Step 5: Prepare for storage
            logger.info("Step 5: Preparing transactions for storage...")
            final_transactions = []
            for tx in categorized_txs:
                final_tx = {
                    "date": tx.get("date"),
                    "amount": float(tx.get("amount", 0)),
                    "currency": tx.get("currency", "INR"),
                    "raw_merchant": tx.get("merchant", "Unknown"),
                    "normalized_merchant": tx.get("normalized_merchant", tx.get("merchant", "Unknown")),
                    "category": tx.get("category", "Other"),
                    "confidence": float(tx.get("confidence", 0.5)),
                    "memo": tx.get("memo", ""),
                }
                final_transactions.append(final_tx)

            logger.info(f"Processing complete: {len(final_transactions)} ready for storage")

            return {
                "success": True,
                "parsed_count": len(parsed_txs),
                "valid_count": len(valid_txs),
                "processed_count": len(final_transactions),
                "transactions": final_transactions,
                "category_distribution": category_dist,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Processing pipeline failed: {str(e)}")
            return {
                "success": False,
                "error": f"Processing pipeline error: {str(e)}",
                "errors": errors,
                "parsed_count": 0,
            }
