"""Chat service with SQL-backed RAG."""

from enum import Enum
from typing import Dict, Any, List
from supabase import Client
import requests
from app.core.config import get_settings


class IntentType(str, Enum):
    """Chat query intent types."""
    TOTAL_BY_CATEGORY = "total_by_category"
    MERCHANT_BREAKDOWN = "merchant_breakdown"
    PERIOD_COMPARISON = "period_comparison"
    EVENT_QUERY = "event_query"
    OPEN_ENDED = "open_ended"


def classify_intent(question: str) -> IntentType:
    """
    Classify chat query intent using keyword matching.

    Args:
        question: User's natural language question

    Returns:
        Intent type classification
    """
    q_lower = question.lower()

    if any(kw in q_lower for kw in ["total", "spent", "spend", "amount"]):
        if any(kw in q_lower for kw in ["category", "type", "food", "transport", "shopping"]):
            return IntentType.TOTAL_BY_CATEGORY

    if any(kw in q_lower for kw in ["merchant", "store", "vendor", "where", "which"]):
        return IntentType.MERCHANT_BREAKDOWN

    if any(kw in q_lower for kw in ["compared", "comparison", "vs", "difference", "more than", "last"]):
        return IntentType.PERIOD_COMPARISON

    if any(kw in q_lower for kw in ["trip", "vacation", "event", "event"]):
        return IntentType.EVENT_QUERY

    return IntentType.OPEN_ENDED


async def build_sql_query(
    intent: IntentType,
    user_id: str,
    filters: Dict[str, Any],
) -> str:
    """
    Build parameterized SQL query based on intent.

    Args:
        intent: Classified intent type
        user_id: User UUID
        filters: Query filters (start_date, end_date, category, etc.)

    Returns:
        SQL query string
    """
    if intent == IntentType.TOTAL_BY_CATEGORY:
        return f"""
        SELECT c.name AS category, COALESCE(SUM(t.amount), 0) AS total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = '{user_id}'
        AND t.is_transfer = FALSE
        {f"AND t.date >= '{filters['start_date']}'" if filters.get('start_date') else ""}
        {f"AND t.date <= '{filters['end_date']}'" if filters.get('end_date') else ""}
        GROUP BY c.id, c.name
        ORDER BY total DESC;
        """

    elif intent == IntentType.MERCHANT_BREAKDOWN:
        return f"""
        SELECT t.raw_merchant, COUNT(*) AS count, COALESCE(SUM(t.amount), 0) AS total
        FROM transactions t
        WHERE t.user_id = '{user_id}'
        AND t.is_transfer = FALSE
        {f"AND t.date >= '{filters['start_date']}'" if filters.get('start_date') else ""}
        {f"AND t.date <= '{filters['end_date']}'" if filters.get('end_date') else ""}
        GROUP BY t.raw_merchant
        ORDER BY total DESC
        LIMIT 10;
        """

    elif intent == IntentType.EVENT_QUERY:
        return f"""
        SELECT e.name AS event, COALESCE(SUM(t.amount), 0) AS total
        FROM events e
        LEFT JOIN event_transactions et ON e.id = et.event_id
        LEFT JOIN transactions t ON et.transaction_id = t.id
        WHERE e.user_id = '{user_id}'
        GROUP BY e.id, e.name
        ORDER BY total DESC;
        """

    else:  # OPEN_ENDED or PERIOD_COMPARISON
        return f"""
        SELECT
            DATE_TRUNC('month', t.date) AS month,
            c.name AS category,
            COALESCE(SUM(t.amount), 0) AS total
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = '{user_id}'
        AND t.is_transfer = FALSE
        {f"AND t.date >= '{filters['start_date']}'" if filters.get('start_date') else ""}
        {f"AND t.date <= '{filters['end_date']}'" if filters.get('end_date') else ""}
        GROUP BY DATE_TRUNC('month', t.date), c.id, c.name
        ORDER BY month DESC, total DESC;
        """


async def run_query(
    sql: str,
    db: Client,
) -> Dict[str, Any]:
    """
    Execute SQL query against Supabase.

    Args:
        sql: SQL query string
        db: Supabase client

    Returns:
        Query results as dict
    """
    try:
        response = db.rpc("sql_exec", {"sql": sql}).execute()
        if response.data:
            return {"data": response.data, "success": True}
        return {"data": [], "success": True}
    except Exception as e:
        return {"error": str(e), "success": False}


async def explain_with_llm(
    question: str,
    sql_result: Dict[str, Any],
) -> str:
    """
    Use LLM to explain SQL results in natural language.

    Args:
        question: Original user question
        sql_result: Result from SQL query

    Returns:
        Natural language explanation
    """
    try:
        settings = get_settings()
    except Exception:
        return "I couldn't access system configuration. Please try again later."

    if not sql_result.get("success"):
        return "I couldn't query your data. Please try a different question."

    data = sql_result.get("data", [])
    if not data:
        return "No data found for your query. Try asking about a different time period or category."

    # Format data for LLM context
    context = f"""
    User asked: {question}

    Query results:
    {str(data)[:500]}
    """

    prompt = f"""
    You are a financial assistant. Based on the transaction data provided, answer the user's question in 1-2 sentences.
    Be specific about amounts in INR. Never perform arithmetic yourself - the numbers are already computed.

    {context}

    Answer:
    """

    try:
        response = requests.post(
            f"{settings.openrouter_api_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Personal Finance OS",
            },
            json={
                "model": settings.primary_llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
            },
            timeout=10,
        )

        if response.status_code == 200:
            answer = response.json()["choices"][0]["message"]["content"]
            return answer.strip()
    except Exception as e:
        return f"I found your data but couldn't generate a response: {str(e)}"

    return "Unable to explain your results."


async def stream_chat_response(
    question: str,
    user_id: str,
    db: Client,
):
    """
    Stream a chat response using SQL + LLM.

    Args:
        question: User's question
        user_id: User UUID
        db: Supabase client

    Yields:
        Response tokens
    """
    intent = classify_intent(question)
    sql = await build_sql_query(intent, user_id, {})
    result = await run_query(sql, db)
    explanation = await explain_with_llm(question, result)

    # Stream explanation word by word (or character by character for demo)
    for char in explanation:
        yield f"data: {char}\n\n"
