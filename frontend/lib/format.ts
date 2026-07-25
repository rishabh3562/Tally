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
