"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useWard } from "@/app/providers";
import { api } from "@/lib/api";
import { inr } from "@/lib/format";
import { cn } from "@/lib/utils";

// The navigation follows the brief's questions. Add a page: create app/<route>/page.tsx and add it here.
export const NAV = [
  { href: "/", label: "Where did the money go?" },
  { href: "/case", label: "Follow one case" },
  { href: "/audit", label: "What doesn't add up?" },
  { href: "/scorecards", label: "Who is responsible?" },
  { href: "/next-rupee", label: "Where should the next rupee go?" },
  { href: "/ask", label: "Ask about my complaint" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { ward, setWard } = useWard();
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => api("/overview") });
  const wards = useQuery({ queryKey: ["wards"], queryFn: () => api("/wards") });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api("/health") });
  const o = overview.data;
  const w = wards.data?.rows?.find((r: any) => r.ward_code === ward);

  return (
    <div className="min-h-screen bg-[#F6F6F3] text-[#16181D]">
      <header className="mx-auto max-w-[1280px] px-5 pt-5">
        {/* Hero: the whole pitch on first paint. Illustration generated with Codex (public/hero.png). */}
        <div
          className="relative overflow-hidden rounded-2xl bg-[#16181D] px-7 py-6 text-[#F6F6F3]"
          style={{
            backgroundImage:
              "linear-gradient(90deg,#16181D 0%,#16181D 52%,rgba(22,24,29,.6) 72%,rgba(22,24,29,.05) 100%),url(/hero.png)",
            backgroundSize: "cover",
            backgroundPosition: "right center",
          }}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-[13px] font-semibold tracking-wide text-[#C9CBD1]">
              <span className="text-[17px] font-extrabold text-white">Nagar</span>
              <span className="text-[17px] font-extrabold text-[#FF9B6A]">Lens</span>
              <span className="ml-2">Follow every rupee from a complaint to a fix that held</span>
            </div>
            <div className="flex items-center gap-2 text-[12px]">
              <span className="rounded-full bg-white/10 px-2.5 py-1">
                {health.data?.ai_available ? `AI: ${health.data.ai_engine}` : "AI offline: cached answers + templates"}
              </span>
              <label className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 font-semibold text-[#16181D]">
                Ward
                <select value={ward} onChange={(e) => setWard(e.target.value)} className="max-w-[210px] bg-transparent outline-none" aria-label="Ward">
                  {(wards.data?.rows ?? [{ ward_code: "L", ward_name: "Kurla" }]).map((r: any) => (
                    <option key={r.ward_code} value={r.ward_code}>
                      {r.ward_code} · {r.ward_name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-end gap-x-7 gap-y-3">
            <Stat label="Billed for 2025 monsoon road repairs" value={o ? inr(o.billed_inr) : "…"} />
            <span className="pb-1 text-[26px] text-[#8A8F98]">→</span>
            <Stat label="Needs a second look (3 rules, counted once)" value={o ? inr(o.review.total_at_risk_inr) : "…"} tone="#FF9B6A" />
            <span className="pb-1 text-[26px] text-[#8A8F98]">→</span>
            <Stat
              label={w ? `Ward ${ward}: ${inr(w.total_review_inr)} to review, then reinvest by risk` : "Recover, then reinvest by risk"}
              value="Next rupee plan"
              tone="#7FD99A"
            />
          </div>
          <div className="mt-3 text-[11.5px] text-[#C9CBD1]">
            Synthetic organizer data · all contractors fictional · leads for review, not accusations
          </div>
        </div>
        <nav className="mt-4 flex flex-wrap gap-1 border-b border-[#D5D6D0]">
          {NAV.map((n) => {
            const active = n.href === "/" ? path === "/" : path.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "rounded-t-lg px-3.5 py-2 text-[13.5px] font-semibold",
                  active ? "border-b-[3px] border-[#1E4FD8] text-[#1E4FD8]" : "text-[#454952] hover:text-[#16181D]",
                )}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="mx-auto max-w-[1280px] px-5 py-5">{children}</main>
      <footer className="mx-auto max-w-[1280px] px-5 pb-8 text-[12px] text-[#454952]">
        NagarLens · Team 11 · Claude Impact Lab Mumbai · Dataset: “Follow the Rupee: Mumbai Monsoon Roads” (synthetic, CC BY 4.0). Do not
        use this to judge any real person, contractor or department.
      </footer>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="text-[12px] text-[#C9CBD1]">{label}</div>
      <div className="text-[30px] font-extrabold leading-tight" style={{ color: tone ?? "#FFFFFF" }}>
        {value}
      </div>
    </div>
  );
}
