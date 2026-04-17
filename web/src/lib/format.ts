// Formatting helpers — pure functions, safe in client and server contexts.
// Do NOT import 'fs' or 'path' here.

export function formatAmount(raw: number): string {
  const millions = raw / 1_000_000;
  if (millions >= 1) {
    return `${millions.toFixed(1).replace(/\.0$/, "")}M CBWD`;
  }
  const thousands = raw / 1_000;
  return `${thousands.toFixed(0)}K CBWD`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
