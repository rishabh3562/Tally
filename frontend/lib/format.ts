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

/** A single transaction's amount, signed the way the person experienced it.
 *
 *  Storage and reading are opposite here: a payment OUT is stored positive
 *  (`amount > 0` means money left the account) and money IN is stored negative.
 *  Printed raw that reads backwards — a ₹500 refund appeared as "-₹500", which
 *  looks like a charge. So the display flips it: money in is +, money out is −.
 *  Zero takes no sign.
 *
 *  For a total that is spending by definition (a category total, a group total)
 *  use `formatINR` — a sign there says nothing and only adds noise. */
export function formatSignedINR(value: number | null | undefined): string {
  const n = Number(value || 0);
  const sign = n < 0 ? "+" : n > 0 ? "−" : "";
  return `${sign}₹${formatAmount(Math.abs(n))}`;
}

/** Colour for the same figure: money in green, money out red, zero neutral.
 *  Paired with `formatSignedINR` so the sign and the colour can never disagree. */
export function amountToneClass(value: number | null | undefined): string {
  const n = Number(value || 0);
  if (n < 0) return "text-emerald-600";
  if (n > 0) return "text-red-600";
  return "text-gray-900";
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
