"""Agent for parsing bank statements into structured transactions."""

import json
import logging
from typing import Any, Dict, List
from app.agents.base import FinancialAgent, AgentResult, LLMConfig

logger = logging.getLogger(__name__)


class ParsingAgent(FinancialAgent):
    """Agent specialized in parsing bank statements."""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config, "ParsingAgent")

    async def run(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Parse raw transaction data from statement.

        Input: {
            "raw_transactions": [list of dict],
            "bank_code": str,
            "file_type": str (pdf|csv|xlsx)
        }

        Output: {
            "parsed_count": int,
            "transactions": [{date, amount, merchant, memo, currency}],
            "errors": [str]
        }
        """
        try:
            raw_transactions = input_data.get("raw_transactions", [])
            bank_code = input_data.get("bank_code", "UNKNOWN")
            file_type = input_data.get("file_type", "unknown")

            if not raw_transactions:
                return AgentResult(
                    success=False,
                    error="No raw transactions provided",
                )

            self._log(f"Parsing {len(raw_transactions)} transactions from {bank_code}")

            # Use LLM to validate and normalize transaction structure
            prompt = f"""Analyze these raw transactions from a {bank_code} bank statement ({file_type} file).
Ensure each has: date (YYYY-MM-DD), amount (number), merchant (string), memo (string), currency.
Fix formatting issues and return as JSON array.

Raw transactions:
{json.dumps(raw_transactions[:10], indent=2)}

Return ONLY valid JSON array with normalized transactions:"""

            response = await self.llm.call(
                prompt=prompt,
                system_prompt="You are a financial data parser. Normalize transaction data to standard format.",
                json_mode=True,
            )

            try:
                parsed = json.loads(response)
                if isinstance(parsed, list):
                    transactions = parsed
                else:
                    transactions = parsed.get("transactions", [])
            except json.JSONDecodeError:
                # Fallback: treat raw transactions as already parsed
                transactions = raw_transactions

            self._log(f"Successfully parsed {len(transactions)} transactions")

            return AgentResult(
                success=True,
                data={
                    "parsed_count": len(transactions),
                    "transactions": transactions,
                    "bank_code": bank_code,
                    "file_type": file_type,
                },
            )

        except Exception as e:
            self._log(f"Parsing failed: {str(e)}")
            return AgentResult(
                success=False,
                error=f"Parsing error: {str(e)}",
            )


class ValidationAgent(FinancialAgent):
    """Agent for validating parsed transactions."""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config, "ValidationAgent")

    async def run(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Validate parsed transactions.

        Input: {
            "transactions": [list of dicts]
        }

        Output: {
            "valid_count": int,
            "invalid_count": int,
            "valid_transactions": [list],
            "issues": [str]
        }
        """
        try:
            transactions = input_data.get("transactions", [])

            if not transactions:
                return AgentResult(
                    success=True,
                    data={
                        "valid_count": 0,
                        "invalid_count": 0,
                        "valid_transactions": [],
                        "issues": [],
                    },
                )

            # Use LLM to validate transaction structure
            validation_prompt = f"""Review these {len(transactions)} transactions for data quality issues:
- All required fields present?
- Dates in YYYY-MM-DD format?
- Amounts are valid numbers?
- Merchants are non-empty?

Transactions sample:
{json.dumps(transactions[:5], indent=2)}

Return JSON with:
{{"issues": [list of issues], "valid_count": int, "invalid_count": int}}"""

            response = await self.llm.call(
                prompt=validation_prompt,
                system_prompt="You are a data quality validator for financial transactions.",
                json_mode=True,
            )

            try:
                validation_result = json.loads(response)
            except json.JSONDecodeError:
                validation_result = {
                    "issues": [],
                    "valid_count": len(transactions),
                    "invalid_count": 0,
                }

            self._log(
                f"Validated {validation_result.get('valid_count', len(transactions))} transactions"
            )

            return AgentResult(
                success=True,
                data={
                    "valid_count": validation_result.get("valid_count", len(transactions)),
                    "invalid_count": validation_result.get("invalid_count", 0),
                    "valid_transactions": transactions,
                    "issues": validation_result.get("issues", []),
                },
            )

        except Exception as e:
            self._log(f"Validation failed: {str(e)}")
            return AgentResult(
                success=False,
                error=f"Validation error: {str(e)}",
            )
