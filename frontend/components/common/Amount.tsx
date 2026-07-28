import { amountToneClass, formatSignedINR } from "@/lib/format";

/**
 * One transaction's amount: signed and coloured from the same number, so the two
 * can never contradict each other. Money in reads `+₹500` in green, money out
 * `−₹500` in red.
 *
 * Only for a single transaction. A total that is spending by definition — a
 * category, a group, a month — takes plain `formatINR`: a minus sign on every
 * row of a spending breakdown says nothing and shouts it.
 */
export default function Amount({
  value,
  className = "",
}: {
  value: number | null | undefined;
  className?: string;
}) {
  return (
    <span className={`tabular-nums ${amountToneClass(value)} ${className}`}>
      {formatSignedINR(value)}
    </span>
  );
}
