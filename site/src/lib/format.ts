const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** yyyymm -> months since year 0, so the x axis is linear in time. */
export function monthOrdinal(yyyymm: number): number {
  return Math.floor(yyyymm / 100) * 12 + (yyyymm % 100) - 1;
}

export function ordinalToYyyymm(ordinal: number): number {
  const year = Math.floor(ordinal / 12);
  return year * 100 + (ordinal - year * 12) + 1;
}

export function formatMonth(yyyymm: number): string {
  return `${MONTH_NAMES[(yyyymm % 100) - 1]} ${Math.floor(yyyymm / 100)}`;
}

export function formatYear(yyyymm: number): string {
  return String(Math.floor(yyyymm / 100));
}

/** Price wedges are logs; show them as percentages, which is how the paper reads them. */
export function formatWedge(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : "−"}${Math.abs(value * 100).toFixed(digits)}%`;
}

export function formatPercentile(value: number): string {
  if (!Number.isFinite(value)) return "—";
  const rank = Math.round(value * 100);
  return `${rank}${ordinalSuffix(rank)}`;
}

function ordinalSuffix(n: number): string {
  if (n % 100 >= 11 && n % 100 <= 13) return "th";
  return ["th", "st", "nd", "rd"][n % 10] ?? "th";
}

export function formatMarketCap(millions: number): string {
  if (!Number.isFinite(millions)) return "—";
  if (millions >= 1_000_000) return `$${(millions / 1_000_000).toFixed(2)}tn`;
  if (millions >= 1_000) return `$${(millions / 1_000).toFixed(1)}bn`;
  return `$${millions.toFixed(0)}m`;
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(0)} KB`;
  return `${bytes} B`;
}

export function formatCount(n: number): string {
  return n.toLocaleString("en-US");
}
