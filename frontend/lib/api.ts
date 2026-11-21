/* eslint-disable @typescript-eslint/no-explicit-any */
// Thin client for the FastAPI backend. Every number shown in the UI comes from these endpoints;
// the frontend never computes totals of its own.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Json = Record<string, any>;

export async function api<T = Json>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

// Ward codes contain "/" (F/N, K/E). The API routes use a path converter, so the code goes in unencoded.
export const wardPath = (ward: string) => `/wards/${ward}`;

export const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const RULE_COLOR: Record<string, string> = {
  overbilled_vs_rate_card: "#C2410C",
  duplicate_bill: "#0F766E", // teal: blue is reserved for selection
  dlp_paid_by_bmc: "#5B4BC4",
  reopened_fix: "#8A5A00",
  sla_missed: "#6A6F78",
};

export const DECISION_LABEL: Record<string, string> = {
  release_payment: "Release payment",
  hold_for_evidence: "Hold for evidence",
  return_under_warranty: "Return under warranty",
};
