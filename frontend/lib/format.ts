// One place for money formatting so the Indian-locale + no-decimals rule can't
// drift between pages (it was copy-pasted into half a dozen files).

/** Indian-grouped amount with no decimals, no symbol — e.g. 12345 → "12,345". */
export function formatAmount(value: number | null | undefined): string {
  return Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

/** Same, prefixed with ₹ — e.g. 12345 → "₹12,345". */
export function formatINR(value: number | null | undefined): string {
  return `₹${formatAmount(value)}`;
}

/** Short form for chart axes, in Indian units (lakh/crore, not million):
 *  12345 → "₹12.3k", 250000 → "₹2.5L", 12000000 → "₹1.2Cr". A full
 *  "₹12,00,000" tick is wider than the bar it labels on a phone. */
export function formatINRCompact(value: number | null | undefined): string {
  const n = Number(value || 0);
  const abs = Math.abs(n);
  if (abs >= 1e7) return `₹${(n / 1e7).toFixed(1)}Cr`;
  if (abs >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`;
  if (abs >= 1e3) return `₹${(n / 1e3).toFixed(1)}k`;
  return `₹${Math.round(n)}`;
}
