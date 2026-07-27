import type { ChatTrace, ChatTraceStep } from '@/types';

export interface DrillLink {
  label: string;
  href: { pathname: string; query: Record<string, string> };
}

/** Turn an answer's tool calls into links to the transactions behind it.
 *
 *  The Palantir move: an answer is never a dead end — the figures came from rows,
 *  so offer the rows. The arguments the tool was called with ARE the filter, so
 *  no guessing from the answer text.
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
