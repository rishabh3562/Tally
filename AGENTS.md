# LangGraph + LangChain Agentic System

## Overview

The Personal Finance OS now features a sophisticated multi-agent system powered by LangGraph and LangChain, using **Nemotron 3 Ultra** as the primary LLM via OpenRouter.

## Architecture

The agentic system consists of specialized agents for different tasks:

### 1. **Parsing Agent** (`ParsingAgent`)
- **Purpose**: Extract transactions from bank statements
- **Input**: Raw transactions, bank code, file type
- **Output**: Normalized JSON transaction objects
- **Uses Nemotron 3 Ultra for**: Validating and fixing transaction formatting

### 2. **Validation Agent** (`ValidationAgent`)
- **Purpose**: Quality-check parsed transactions
- **Input**: Parsed transactions
- **Output**: Valid/invalid counts, issues identified
- **Uses Nemotron 3 Ultra for**: Detecting data quality issues

### 3. **Merchant Normalization Agent** (`MerchantNormalizationAgent`)
- **Purpose**: Convert raw merchant strings to canonical names
- **Input**: Transactions with raw merchant names
- **Output**: Normalized merchant names, merchant mappings
- **Examples**:
  - `SBUX 4432` → `Starbucks`
  - `UBER*TRIP` → `Uber`
  - `HDFC ATM #1234` → `HDFC ATM`
- **Uses Nemotron 3 Ultra for**: Learning merchant patterns and applying them consistently

### 4. **Categorization Agent** (`CategorizationAgent`)
- **Purpose**: Assign transactions to expense categories
- **Input**: Normalized transactions
- **Output**: Transactions with category + confidence score
- **Categories**: Food & Dining, Transport, Shopping, Groceries, Subscriptions, Healthcare, Education, Travel, Entertainment, Utilities, Other
- **Uses Nemotron 3 Ultra for**: Context-aware categorization with confidence scoring

### 5. **Analytics Agent** (`AnalyticsAgent`)
- **Purpose**: Generate financial insights and answer queries
- **Input**: Question + transactions + optional SQL results
- **Output**: Detailed analysis with metrics
- **Uses Nemotron 3 Ultra for**: Natural language analysis and explanation

### 6. **Event Summary Agent** (`EventSummaryAgent`)
- **Purpose**: Summarize spending events/case studies
- **Input**: Event name + transactions
- **Output**: Summary + breakdown + key insights
- **Uses Nemotron 3 Ultra for**: Generating insightful event summaries

## Pipeline Orchestration

The `FinancialProcessingOrchestrator` coordinates all agents in sequence:

```
Raw File → Parser → Validator → Merchant Normalizer → Categorizer → Storage
                                                                        ↓
                                        Analytics + Event Summary Agents
```

## Configuration

### Environment Variables

Set in `.env`:

```bash
# OpenRouter API Configuration
OPENROUTER_API_KEY=your_openrouter_key_here

# Primary model (Nemotron 3 Ultra)
PRIMARY_LLM_MODEL=neomorph/nemotron-3-ultra

# Secondary fallback
SECONDARY_LLM_MODEL=anthropic/claude-3-5-sonnet
FALLBACK_LLM_MODEL=google/gemini-2.0-flash-exp
```

### Getting an OpenRouter Key

1. Go to [openrouter.ai](https://openrouter.ai)
2. Sign up for an account
3. Add payment method (Nemotron 3 Ultra is cost-efficient)
4. Copy your API key
5. Add to `.env` as `OPENROUTER_API_KEY`

## Usage Examples

### Processing a Bank Statement

```python
from app.agents.orchestrator import FinancialProcessingOrchestrator
from app.agents.base import LLMConfig

llm_config = LLMConfig(
    api_key="your_openrouter_key",
    model="neomorph/nemotron-3-ultra"
)

orchestrator = FinancialProcessingOrchestrator(llm_config)

result = await orchestrator.process_statement(
    raw_transactions=raw_txs,
    bank_code="HDFC",
    file_type="csv"
)
```

### Custom Agent Usage

```python
from app.agents.analytics_agent import AnalyticsAgent
from app.agents.base import LLMConfig

llm_config = LLMConfig(api_key="key", model="neomorph/nemotron-3-ultra")
agent = AnalyticsAgent(llm_config)

result = await agent.run({
    "question": "How much did I spend on food?",
    "transactions": [...],
    "sql_results": {food_total: 12400}
})
```

## Agent Response Format

All agents follow this format:

```python
AgentResult(
    success: bool,
    data: dict = {
        # Agent-specific output
    },
    error: str = None
)
```

### To Dict

```python
result.to_dict()
# Returns:
# {
#     "success": True/False,
#     "data": {...},
#     "error": "error message if any"
# }
```

## Why Nemotron 3 Ultra?

✅ **Fast**: Excellent latency for real-time processing
✅ **Cost-Effective**: Low per-token pricing via OpenRouter
✅ **Reliable**: Consistent results for financial data
✅ **Fallback**: Automatic fallback to Claude/Gemini if rate-limited
✅ **Flexible**: Works with JSON mode for structured outputs

## Extending with New Agents

Create new agents by extending `FinancialAgent`:

```python
from app.agents.base import FinancialAgent, AgentResult, LLMConfig

class MyCustomAgent(FinancialAgent):
    def __init__(self, llm_config: LLMConfig):
        super().__init__(llm_config, "MyCustomAgent")

    async def run(self, input_data: dict) -> AgentResult:
        # Your agent logic here
        try:
            # Use self.llm.call() to invoke Nemotron 3 Ultra
            response = await self.llm.call(prompt="your prompt")
            
            return AgentResult(
                success=True,
                data={"result": response}
            )
        except Exception as e:
            return AgentResult(success=False, error=str(e))
```

## Monitoring & Logging

All agents log their activities:

```
[ParsingAgent] Parsing 150 transactions from HDFC
[ParsingAgent] Successfully parsed 150 transactions
[MerchantNormalizationAgent] Normalizing 127 unique merchants
[MerchantNormalizationAgent] Normalized 150 merchants
[CategorizationAgent] Categorizing 150 transactions
[CategorizationAgent] Categorized 150 transactions
```

Check `backend/logs/` for detailed agent execution logs.

## Error Handling

Agents gracefully handle failures with fallbacks:

1. **Parsing**: Falls back to raw transaction format
2. **Validation**: Returns as-is if validation fails
3. **Normalization**: Uses original merchant name if normalization fails
4. **Categorization**: Defaults to "Other" if categorization fails

This ensures the pipeline continues despite partial failures.

## Performance

Typical processing times for a statement:

- Parsing: 0.5-1s (depends on file size)
- Validation: 0.2-0.5s
- Normalization: 1-2s (unique merchants)
- Categorization: 2-3s (transactions)
- **Total**: ~5-10s for 100-200 transactions

## Future Enhancements

Planned agents:

- **Budget Alert Agent**: Monitor spending against budgets
- **Anomaly Detection Agent**: Flag unusual transactions
- **Forecast Agent**: Predict future spending patterns
- **Recommendation Agent**: Suggest savings opportunities
- **Reporting Agent**: Generate monthly/quarterly reports

## Troubleshooting

### "401 Unauthorized" from OpenRouter

→ Check `OPENROUTER_API_KEY` is correct in `.env`

### Agent returns low confidence scores

→ Try with simpler transactions or check merchant formatting

### Timeout errors

→ Increase timeout in `LLMConfig(timeout=...)`

### Rate limiting

→ Add multiple keys to `OPENROUTER_API_KEYS` (comma-separated)

## API Endpoints

### Upload & Process

```bash
POST /api/upload-statement
- file: bank statement (PDF/CSV/Excel)
- account_id: target account UUID
- bank_code: HDFC, ICICI, SBI, etc.

# Response
{
  "job_id": "uuid",
  "status": "queued",
  "message": "Processing started"
}
```

### Check Job Status

```bash
GET /api/jobs/{job_id}

# Response
{
  "job_id": "uuid",
  "status": "done|processing|failed",
  "error": null,
  "created_at": "2026-06-27T...",
  "finished_at": "2026-06-27T..."
}
```

All agent output is automatically saved to Supabase and queryable via the dashboard.
