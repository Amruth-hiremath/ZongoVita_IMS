/**
 * Display formatting. The API carries quantities and money as decimal strings (LLD section 12);
 * they are formatted only here, for display, and never parsed back for arithmetic.
 */

const quantity = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 4 });
const money = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

/** "2400" -> "2,400"; "12.5000" -> "12.5". */
export function formatQty(value: string | number): string {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? quantity.format(number) : String(value);
}

/** "4286400" -> "₹42,86,400" in the customer's single currency (INR by default, LD-71). */
export function formatMoney(value: string | number, symbol = "₹"): string {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? `${symbol}${money.format(number)}` : String(value);
}

/** Signed quantity for variances and movements: "+8", "−4" (true minus sign, as in the frames). */
export function formatSigned(value: string | number): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return String(value);
  if (number === 0) return "0";
  return `${number > 0 ? "+" : "−"}${quantity.format(Math.abs(number))}`;
}
