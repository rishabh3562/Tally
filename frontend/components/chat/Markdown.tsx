"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Assistant answers rendered as GitHub-flavoured markdown — tables, bold figures,
 * lists — instead of one flat paragraph. A breakdown of eight categories is a
 * table; as `whitespace-pre-wrap` text it was a wall.
 *
 * Every element carries an EXPLICIT text colour. The app is light-only and this
 * markup is generated, not hand-written, so there is no call site to fix later if
 * a colour is inherited (see CLAUDE.md).
 *
 * No `rehype-raw`: react-markdown does not render embedded HTML by default, and
 * this content comes from an LLM. Keep it that way — the model's output is not
 * trusted markup.
 */

const components: Components = {
  // Paragraphs stack with a gap, but the first one sits flush with the bubble.
  p: ({ children }) => (
    <p className="break-words text-sm leading-relaxed text-gray-900 [&:not(:first-child)]:mt-2">
      {children}
    </p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-gray-900">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-gray-900">{children}</em>,
  ul: ({ children }) => (
    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-900">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-gray-900">{children}</ol>
  ),
  li: ({ children }) => <li className="text-sm text-gray-900">{children}</li>,

  // A table must scroll inside the bubble — never widen it. min-w-max keeps
  // columns on one line and lets the wrapper take the overflow.
  table: ({ children }) => (
    // White on the bubble's grey so the table reads as its own object.
    <div className="my-2 overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="w-full min-w-max border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
  tr: ({ children }) => <tr className="border-b border-gray-200 last:border-0">{children}</tr>,
  // `style` carries GFM column alignment (|---:| → right) — spread it through so
  // amount columns stay right-aligned.
  th: ({ children, style }) => (
    <th
      style={style}
      className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
    >
      {children}
    </th>
  ),
  td: ({ children, style }) => (
    <td style={style} className="whitespace-nowrap px-3 py-2 text-gray-900 tabular-nums">
      {children}
    </td>
  ),

  // Headings inside a chat bubble are section labels, not page titles — one size.
  h1: ({ children }) => <p className="mt-3 text-sm font-semibold text-gray-900">{children}</p>,
  h2: ({ children }) => <p className="mt-3 text-sm font-semibold text-gray-900">{children}</p>,
  h3: ({ children }) => <p className="mt-3 text-sm font-semibold text-gray-900">{children}</p>,

  code: ({ children }) => (
    <code className="rounded bg-gray-200 px-1 py-0.5 font-mono text-[0.85em] text-gray-800">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-100">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-gray-300 pl-3 text-sm text-gray-700">
      {children}
    </blockquote>
  ),
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-blue-700 underline underline-offset-2 hover:text-blue-800"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-3 border-gray-200" />,
};

/**
 * Protect merchant names from the markdown parser.
 *
 * Indian card/UPI descriptors are full of asterisks — `PAYTM*SWIGGY*BLR`,
 * `GOOGL*SERV*IN` — and markdown reads the pair as emphasis, so the name renders
 * as "PAYTMSWIGGYBLR" with the middle italic. The asterisks are silently gone and
 * the name no longer matches the statement it came from.
 *
 * So escape an asterisk that sits BETWEEN two non-space characters. Real emphasis
 * from the model is always at a word boundary (`**Rs 4,556**`, `*maybe*`), and the
 * `[^\s*]` on both sides leaves the doubled asterisks of bold alone. Underscores
 * need no such care: CommonMark already refuses intraword `_`, so
 * `UPI_TRANSFER_XYZ` survives on its own.
 */
function escapeIntrawordAsterisks(text: string): string {
  return text.replace(/([^\s*])\*(?=[^\s*])/g, "$1\\*");
}

export default function Markdown({ children }: { children: string }) {
  return (
    <div className="min-w-0 text-sm text-gray-900">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {escapeIntrawordAsterisks(children)}
      </ReactMarkdown>
    </div>
  );
}
