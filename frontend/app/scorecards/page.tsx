"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { DataBadge, ErrorBox, Loading, PageTitle, PeerChip, Section } from "@/components/bits";
import { api } from "@/lib/api";
import { inr, pct } from "@/lib/format";

export default function ScorecardsPage() {
  const [kind, setKind] = useState<"contractors" | "wards">("contractors");
  const q = useQuery({ queryKey: ["scorecards", kind], queryFn: () => api(`/scorecards/${kind}`) });
  const tiers = useQuery({ queryKey: ["sla-tiers"], queryFn: () => api("/scorecards/sla-tiers") });
  if (q.error) return <ErrorBox error={q.error} />;
  if (!q.data) return <Loading />;

  return (
    <div className="space-y-5">
      <PageTitle title="Who is responsible? Fair, like-for-like scorecards" sub="Each contractor and ward is compared with what everyone else achieves on the same mix of jobs." />
      <div className="rounded-xl border border-[#A9BEF0] bg-[#EEF3FD] px-4 py-3 text-[13.5px]">
        <b>System problem, not a contractor problem:</b> 24-hour SLAs are missed on almost every job by everyone, and warranty-period billing
        is spread across all eight contractors. Those are process gaps, so they never count against one contractor.
      </div>
      <div className="flex gap-2">
        {(["contractors", "wards"] as const).map((k) => (
          <button key={k} onClick={() => setKind(k)} className={`rounded-full border px-4 py-1.5 text-[13px] font-semibold capitalize ${kind === k ? "border-[#1E4FD8] bg-[#E3EBFD] text-[#17306E]" : "border-[#D5D6D0] bg-white"}`}>{k}</button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {q.data.rows.map((r: any) => (
          <div key={r.contractor_id ?? r.ward_code} className="rounded-2xl border border-[#D5D6D0] bg-white p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-[16px] font-extrabold">{kind === "wards" ? `Ward ${r.ward_code} · ${r.ward_name}` : r.contractor}</div>
                <div className="text-[12.5px] text-[#454952]">{r.jobs} repairs · {inr(r.billed_inr)} billed · {r.durability_tier}{r.small_sample ? " · small sample" : ""}</div>
              </div>
              <DataBadge />
            </div>
            <div className="my-3 flex gap-2">
              <PeerChip label="Speed" value={r.speed_chip} />
              <PeerChip label="Durability" value={r.durability_chip} />
              <PeerChip label="Cost" value={r.cost_chip} />
            </div>
            <div className="grid grid-cols-3 gap-2 text-[12.5px]">
              <Versus label="On time" actual={r.on_time_rate} expected={r.expected_on_time_rate} higherIsBetter />
              <Versus label="Re-opened in 30 days" actual={r.reopen_rate} expected={r.expected_reopen_rate} />
              <Versus label="Bills above 1.4× rate card" actual={r.over_rate_card_share} expected={r.peer_over_rate_card_share} />
            </div>
            <p className="mt-3 text-[13.5px] leading-relaxed">{r.text}</p>
          </div>
        ))}
      </div>

      {tiers.data ? (
        <Section title="On time within each SLA tier: urgent jobs are late for everyone" hint="Share of jobs finished inside the SLA. Darker = more often on time.">
          <table className="w-full text-center text-[13px]">
            <thead><tr><th className="text-left">Contractor</th>{tiers.data.tiers.map((t: number) => <th key={t} className="py-1">{t} h</th>)}</tr></thead>
            <tbody>
              {tiers.data.rows.map((row: any) => (
                <tr key={row.contractor} className={row.contractor === "All contractors" ? "font-bold" : ""}>
                  <td className="py-1 pr-3 text-left">{row.contractor}</td>
                  {row.cells.map((c: any) => (
                    <td key={c.sla_hours} className="p-0.5">
                      <div className="rounded py-1.5" title={`${c.jobs} jobs`} style={{ background: `rgba(30,79,216,${0.06 + 0.84 * c.on_time_rate})`, color: c.on_time_rate > 0.5 ? "#fff" : "#16181D" }}>{pct(c.on_time_rate)}</div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div aria-label="Legend" className="mt-3 flex items-center justify-end gap-2 text-[12.5px] text-[#2A2D33]">
            <span>Share finished inside the SLA:</span>
            {[0, 0.25, 0.5, 0.75, 1].map((v) => (
              <span key={v} className="flex flex-col items-center">
                <span className="inline-block h-3 w-9 rounded-sm" style={{ background: `rgba(30,79,216,${0.06 + 0.84 * v})` }} />
                <span className="text-[11px] text-[#454952]">{Math.round(v * 100)}%</span>
              </span>
            ))}
          </div>
        </Section>
      ) : null}

      <Section title="How the comparison is made fair">
        <ul className="list-disc space-y-1 pl-5 text-[13px] text-[#2A2D33]">{q.data.method.map((m: string) => <li key={m}>{m}</li>)}</ul>
      </Section>
    </div>
  );
}

function Versus({ label, actual, expected, higherIsBetter }: { label: string; actual: number; expected: number; higherIsBetter?: boolean }) {
  const better = higherIsBetter ? actual >= expected : actual <= expected;
  return (
    <div className="rounded-lg bg-[#F6F6F3] px-2.5 py-2">
      <div className="text-[11px] text-[#454952]">{label}</div>
      <div className="text-[18px] font-extrabold" style={{ color: better ? "#1E7B34" : "#B07A00" }}>{pct(actual)}</div>
      <div className="text-[11px] text-[#454952]">peers on same mix: {pct(expected)}</div>
    </div>
  );
}
