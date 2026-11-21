// Display helpers. Amounts arrive as integer rupees; these only format, never compute.
export function inr(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  const a = Math.abs(x);
  if (a >= 1e7) return `₹${(x / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `₹${(x / 1e5).toFixed(1)} L`;
  return `₹${Math.round(x).toLocaleString("en-IN")}`;
}

export const inrFull = (x: number | null | undefined) =>
  x === null || x === undefined ? "–" : `₹${Math.round(x).toLocaleString("en-IN")}`;

export const pct = (x: number | null | undefined, digits = 0) =>
  x === null || x === undefined ? "–" : `${(x * 100).toFixed(digits)}%`;

export function when(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hour12: false } : {}),
  });
}

export const cleanName = (s: string | null | undefined) => (s ?? "").replace(" (synthetic)", "");
