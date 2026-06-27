"""Agents for merchant normalization and transaction categorization."""

import json
import logging
from typing import Any, Dict
from app.agents.base import FinancialAgent, AgentResult, LLMConfig

logger = logging.getLogger(__name__)


class MerchantNormalizationAgent(FinancialAgent):
    """Agent for normalizing merchant names."""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config, "MerchantNormalizationAgent")

    async def run(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Normalize merchant names.

        Input: {
            "transactions": [{date, amount, merchant, memo, ...}]
        }

        Output: {
            "normalized_transactions": [same + normalized_merchant field],
            "merchant_mappings": {raw: canonical}
        }
        """
        try:
            transactions = input_data.get("transactions", [])

            if not transactions:
                return AgentResult(
                    success=True,
                    data={
                        "normalized_transactions": [],
                        "merchant_mappings": {},
                    },
                )

            # Extract unique merchants
            merchants = list(set(tx.get("merchant", "Unknown") for tx in transactions))
            self._log(f"Normalizing {len(merchants)} unique merchants")

            # Use LLM to normalize merchant names
            normalization_prompt = f"""Normalize these merchant names to canonical forms.
Use common standardized names (e.g., "SBUX 4432" -> "Starbucks", "UBER*TRIP" -> "Uber").

Merchants:
{json.dumps(merchants[:50], indent=2)}

Return JSON: {{"mappings": {{raw_name: canonical_name, ...}}}}"""

            response = await self.llm.call(
                prompt=normalization_prompt,
                system_prompt="You are a merchant name normalizer. Convert raw merchant strings to clean canonical names.",
                json_mode=True,
            )

            try:
                result = json.loads(response)
                mappings = result.get("mappings", {})
            except json.JSONDecodeError:
                # Fallback: use original names
                mappings = {m: m for m in merchants}

            # Apply mappings to transactions
            normalized = []
            for tx in transactions:
                merchant = tx.get("merchant", "Unknown")
                tx_copy = tx.copy()
                tx_copy["normalized_merchant"] = mappings.get(merchant, merchant)
                normalized.append(tx_copy)

            self._log(f"Normalized {len(normalized)} transactions")

            return AgentResult(
                success=True,
                data={
                    "normalized_transactions": normalized,
                    "merchant_mappings": mappings,
                },
            )

        except Exception as e:
            self._log(f"Normalization failed: {str(e)}")
            return AgentResult(
                success=False,
                error=f"Merchant normalization error: {str(e)}",
            )


class CategorizationAgent(FinancialAgent):
    """Agent for categorizing transactions."""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config, "CategorizationAgent")
        self.categories = [
            "Food & Dining",
            "Transport",
            "Shopping",
            "Groceries",
            "Subscriptions",
            "Healthcare",
            "Education",
            "Travel",
            "Entertainment",
            "Utilities",
            "Other",
        ]

    async def run(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Categorize transactions.

        Input: {
            "transactions": [{merchant, amount, memo, ...}]
        }

        Output: {
            "categorized_transactions": [same + category + confidence],
            "category_distribution": {category: count}
        }
        """
        try:
            transactions = input_data.get("transactions", [])

            if not transactions:
                return AgentResult(
                    success=True,
                    data={
                        "categorized_transactions": [],
                        "category_distribution": {},
                    },
                )

            self._log(f"Categorizing {len(transactions)} transactions")

            # Use LLM to categorize transactions
            categorization_prompt = f"""Categorize these transactions into one of these categories:
{', '.join(self.categories)}

For each transaction, provide category and confidence (0-1).

Sample transactions:
{json.dumps(transactions[:10], indent=2)}

Return JSON: {{
    "categorizations": [
        {{"merchant": str, "category": str, "confidence": float}},
        ...
    ]
}}"""

            response = await self.llm.call(
                prompt=categorization_prompt,
                system_prompt=f"""You are a transaction categorization expert.
Categorize spending into: {', '.join(self.categories)}
Be confident (0.8+) when clear, lower (0.5-0.7) for ambiguous cases.""",
                json_mode=True,
            )

            try:
                result = json.loads(response)
                categorizations = result.get("categorizations", [])
            except json.JSONDecodeError:
                # Fallback: categorize all as Other
                categorizations = [
                    {
                        "merchant": tx.get("merchant", "Unknown"),
                        "category": "Other",
                        "confidence": 0.5,
                    }
                    for tx in transactions
                ]

            # Create lookup from merchant to category
            merchant_categories = {
                cat["merchant"]: cat for cat in categorizations
            }

            # Apply categories to transactions
            categorized = []
            category_dist = {}
            for tx in transactions:
                merchant = tx.get("merchant", "Unknown")
                cat_info = merchant_categories.get(
                    merchant,
                    {"category": "Other", "confidence": 0.5},
                )

                tx_copy = tx.copy()
                tx_copy["category"] = cat_info.get("category", "Other")
                tx_copy["confidence"] = cat_info.get("confidence", 0.5)
                categorized.append(tx_copy)

                # Count for distribution
                category = cat_info.get("category", "Other")
                category_dist[category] = category_dist.get(category, 0) + 1

            self._log(f"Categorized {len(categorized)} transactions")

            return AgentResult(
                success=True,
                data={
                    "categorized_transactions": categorized,
                    "category_distribution": category_dist,
                },
            )

        except Exception as e:
            self._log(f"Categorization failed: {str(e)}")
            return AgentResult(
                success=False,
                error=f"Categorization error: {str(e)}",
            )
