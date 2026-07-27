import type { ChatTrace, ChatTraceStep } from '@/types';

export interface DrillLink {
  label: string;
  href: { pathname: string; query: Record<string, string> };
}

/** Did this tool call actually find (or change) anything?
 *
 *  Without this check a chip appears under an answer that says there's nothing
 *  there — "You have no transactions in June 2026" followed by a button to a
 *  guaranteed-empty table. The data ends May 2026 while "today" is July, so every
 *  "this month" question hits it.
 */
function foundSomething(step: ChatTraceStep): boolean {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const r = (step.result ?? {}) as any;
  if (r.no_data_in_period || r.error) return false;

  switch (step.tool) {
    case 'search_transactions':
      return (r.count ?? 0) > 0;
    case 'get_spending_by_category':
      // The no_data flag only fires when the WHOLE period is empty; a period with
      // spend but none in the asked-for category leaves categories: [].
      return Array.isArray(r.categories) ? r.categories.length > 0 : true;
    case 'get_top_merchants':
      return Array.isArray(r.merchants) ? r.merchants.length > 0 : true;
    case 'get_largest_transactions':
      return Array.isArray(r.transactions) ? r.transactions.length > 0 : true;
    case 'get_spending_summary':
      return (r.txn_count ?? 1) > 0;
    case 'categorize_merchant':
      return !r.needs_confirmation && (r.transactions_updated ?? 0) > 0;
    default:
      return true;
  }
}

/** Turn an answer's tool calls into links to the transactions behind it.
 *
 *  The Palantir move: an answer is never a dead end — the figures came from rows,
 *  so offer the rows. The arguments the tool was called with ARE the filter, so
 *  there's no guessing from the answer text.
 */
export function drillLinksFromTrace(trace?: ChatTrace): DrillLink[] {
  const steps: ChatTraceStep[] = trace?.steps ?? [];
  const links: DrillLink[] = [];
  const seen = new Set<string>();

  const add = (label: string, query: Record<string, string>) => {
    const key = JSON.stringify(query);
    if (seen.has(key)) return;
    seen.add(key);
    links.push({ label, href: { pathname: '/transactions', query } });
  };

  const period = (args: Record<string, unknown>) => {
    const q: Record<string, string> = {};
    if (typeof args.start === 'string') q.start = args.start;
    if (typeof args.end === 'string') q.end = args.end;
    return q;
  };

  for (const step of steps) {
    if (!foundSomething(step)) continue;
    const args = (step.args ?? {}) as Record<string, unknown>;

    switch (step.tool) {
      case 'search_transactions': {
        // The tool is brand-aware and so is the transactions search, so the same
        // keyword lands on the same rows.
        const keyword = typeof args.keyword === 'string' ? args.keyword.trim() : '';
        if (keyword) add(`See ${keyword} transactions`, { q: keyword, ...period(args) });
        break;
      }
      case 'get_spending_by_category': {
        const category = typeof args.category === 'string' ? args.category.trim() : '';
        if (category) {
          add(`See ${category} transactions`, { category, ...period(args) });
        } else {
          const p = period(args);
          if (Object.keys(p).length) add('See these transactions', p);
        }
        break;
      }
      case 'categorize_merchant': {
        // After a write, the most useful thing is to SEE that it landed.
        const merchant = typeof args.merchant === 'string' ? args.merchant.trim() : '';
        if (merchant) add(`Check ${merchant} transactions`, { q: merchant });
        break;
      }
      case 'get_spending_summary':
      case 'get_largest_transactions':
      case 'get_top_merchants': {
        const p = period(args);
        if (Object.keys(p).length) add('See these transactions', p);
        break;
      }
      default:
        break;
    }
  }

  // Two links is a helpful offer; five is a menu nobody reads.
  return links.slice(0, 2);
}
