"""Agent for financial insights and analytics queries."""

import json
import logging
from typing import Any, Dict, List
from app.agents.base import FinancialAgent, AgentResult, LLMConfig

logger = logging.getLogger(__name__)


class AnalyticsAgent(FinancialAgent):
    """Agent specialized in financial analysis and insights."""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config, "AnalyticsAgent")

    async def run(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Analyze transactions and provide insights.

        Input: {
            "question": str,
            "transactions": [{date, amount, category, merchant, ...}],
            "sql_results": optional results from SQL query
        }

        Output: {
            "insight": str,
            "analysis_type": str,
            "key_metrics": dict
        }
        """
        try:
            question = input_data.get("question", "")
            transactions = input_data.get("transactions", [])
            sql_results = input_data.get("sql_results", {})

            if not question:
                return AgentResult(
                    success=False,
                    error="No question provided",
                )

            self._log(f"Analyzing: {question}")

            # Prepare context for LLM
            context = {
                "transaction_count": len(transactions),
                "total_amount": sum(float(tx.get("amount", 0)) for tx in transactions),
                "date_range": {
                    "min": min((tx.get("date") for tx in transactions), default="unknown"),
                    "max": max((tx.get("date") for tx in transactions), default="unknown"),
                },
            }

            # If SQL results provided, use them for accuracy
            if sql_results:
                context["sql_analysis"] = sql_results

            analysis_prompt = f"""Answer this financial question based on transaction data.
Question: {question}

Available data:
- {len(transactions)} transactions total
- Total amount: ₹{context['total_amount']:,.2f}
- Date range: {context['date_range']['min']} to {context['date_range']['max']}
- SQL analysis: {json.dumps(sql_results, default=str)[:500] if sql_results else 'None'}

Sample transactions:
{json.dumps(transactions[:5], default=str, indent=2)}

Provide a detailed, specific answer. Include numbers and percentages where relevant.
Do NOT make up data - only use what's provided."""

            response = await self.llm.call(
                prompt=analysis_prompt,
                system_prompt="""You are a financial analyst. Answer questions about spending patterns,
budgets, and financial insights. Be specific with numbers and analysis.
Never make up data or metrics not provided.""",
            )

            self._log(f"Generated insight: {response[:100]}...")

            return AgentResult(
                success=True,
                data={
                    "insight": response,
                    "question": question,
                    "context": context,
                },
            )

        except Exception as e:
            self._log(f"Analysis failed: {str(e)}")
            return AgentResult(
                success=False,
                error=f"Analysis error: {str(e)}",
            )


class EventSummaryAgent(FinancialAgent):
    """Agent for summarizing events/case studies."""

    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config, "EventSummaryAgent")

    async def run(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Generate summary for an event/case study.

        Input: {
            "event_name": str,
            "transactions": [{date, amount, category, merchant, ...}],
            "metadata": optional dict
        }

        Output: {
            "summary": str,
            "breakdown": dict of category: amount,
            "insights": list of strings
        }
        """
        try:
            event_name = input_data.get("event_name", "Event")
            transactions = input_data.get("transactions", [])

            if not transactions:
                return AgentResult(
                    success=True,
                    data={
                        "summary": f"{event_name}: No transactions",
                        "breakdown": {},
                        "insights": [],
                    },
                )

            # Calculate breakdown by category
            breakdown = {}
            for tx in transactions:
                category = tx.get("category", "Other")
                amount = float(tx.get("amount", 0))
                breakdown[category] = breakdown.get(category, 0) + amount

            total = sum(breakdown.values())

            self._log(f"Summarizing event '{event_name}' with {len(transactions)} transactions")

            summary_prompt = f"""Summarize this spending event:

Event: {event_name}
Transactions: {len(transactions)}
Total: ₹{total:,.2f}
Breakdown:
{json.dumps(breakdown, indent=2)}

Sample transactions:
{json.dumps(transactions[:5], indent=2)}

Provide:
1. Brief 1-2 sentence summary
2. 2-3 key insights about the spending
Return as JSON: {{"summary": str, "insights": [str, str, str]}}"""

            response = await self.llm.call(
                prompt=summary_prompt,
                system_prompt="""You are a financial summarizer. Create concise, insightful
summaries of spending events. Highlight unusual patterns or insights.""",
                json_mode=True,
            )

            try:
                result = json.loads(response)
                summary = result.get("summary", f"{event_name}: ₹{total:,.2f}")
                insights = result.get("insights", [])
            except json.JSONDecodeError:
                summary = f"{event_name}: ₹{total:,.2f} across {len(transactions)} transactions"
                insights = []

            # Add category breakdown insight
            if breakdown:
                top_category = max(breakdown, key=breakdown.get)
                top_amount = breakdown[top_category]
                pct = (top_amount / total * 100) if total > 0 else 0
                insights.insert(
                    0,
                    f"Largest category: {top_category} (₹{top_amount:,.2f}, {pct:.1f}%)",
                )

            return AgentResult(
                success=True,
                data={
                    "summary": summary,
                    "breakdown": breakdown,
                    "total": total,
                    "transaction_count": len(transactions),
                    "insights": insights,
                },
            )

        except Exception as e:
            self._log(f"Summary generation failed: {str(e)}")
            return AgentResult(
                success=False,
                error=f"Summary error: {str(e)}",
            )
