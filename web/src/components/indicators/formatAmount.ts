/**
 * formatAmount — shared helper for CBWD token amounts.
 *
 * Examples:
 *   12_500_000 → "12.5M"
 *   1_500_000  → "1.5M"
 *   250_000    → "250K"
 *   1_500      → "1.5K"
 *   800        → "800"
 */
export function formatAmount(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) {
    const v = n / 1_000_000;
    return `${parseFloat(v.toFixed(1))}M`;
  }
  if (abs >= 1_000) {
    const v = n / 1_000;
    return `${parseFloat(v.toFixed(1))}K`;
  }
  return String(n);
}
