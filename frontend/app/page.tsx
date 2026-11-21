"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Bar, CartesianGrid, ComposedChart, Layer, Legend, Line, Rectangle, ResponsiveContainer, Sankey, Tooltip, XAxis, YAxis } from "recharts";

import { DataBadge, ErrorBox, Kpi, Loading, PageTitle, Section } from "@/components/bits";
import { api, wardPath } from "@/lib/api";
import { inr, pct } from "@/lib/format";

import { useWard } from "./providers";

const WardMap = dynamic(() => import("@/components/ward-map"), { ssr: false, loading: () => <Loading label="Loading map…" /> });

const KIND_COLOR: Record<string, string> = { source: "#16181D", work_type: "#8A8F98", held: "#1E7B34", failed: "#B07A00", review: "#C2410C" };

function FlowNode({ x, y, width, height, payload }: any) {
  const left = x < 300;
  return (
    <Layer>
      <Rectangle x={x} y={y} width={width} height={height} fill={KIND_COLOR[payload.kind] ?? "#8A8F98"} radius={2} />
      <text x={left ? x + width + 8 : x - 8} y={y + height / 2} textAnchor={left ? "start" : "end"} dominantBaseline="middle" fontSize={12.5} fill="#16181D">
        <tspan fontWeight={700}>{payload.name}</tspan>
        <tspan fill="#454952"> · {inr(payload.value)}</tspan>
      </text>
    </Layer>
  );
}

export default function OverviewPage() {
  const { ward, setWard } = useWard();
  const wards = useQuery({ queryKey: ["wards"], queryFn: () => api("/wards") });
  const geo = useQuery({ queryKey: ["geo"], queryFn: () => api("/wards/geojson") });
  const detail = useQuery({ queryKey: ["ward", ward], queryFn: () => api(wardPath(ward)) });

  if (detail.error || wards.error) return <ErrorBox error={detail.error ?? wards.error} />;
  if (!detail.data || !wards.data) return <Loading />;
  const d = detail.data;
  const w = d.ward;

  return (
    <div className="space-y-5">
      <PageTitle title={`Where did ${w.ward_name}'s repair money go?`} sub={`Ward ${w.ward_code} · Monsoon 2025 · billed amounts from work orders, not payments`} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Kpi label="Allocated budget" value={inr(w.budget_inr)} sub="Jun–Sep 2025" />
        <Kpi label="Billed (work orders)" value={inr(w.billed_inr)} sub={`${pct(w.billed_vs_budget)} of budget · ${w.jobs} jobs`} tone={w.billed_vs_budget > 1 ? "#C2410C" : undefined} />
        <Kpi label="Spent on fixes that failed" value={inr(w.failed_fix_spend_inr)} sub={`${pct(w.reopen_rate)} re-opened within 30 days`} tone="#B07A00" />
        <Kpi label="Repairs on time" value={pct(w.on_time_rate)} sub={`similar wards manage ${pct(w.expected_on_time_rate)}`} />
        <Kpi label="To review" value={inr(d.review.total_at_risk_inr)} sub={`${d.review.jobs} jobs, counted once`} tone="#C2410C" />
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <Section title="Follow the rupee: what it was spent on, and whether it held" hint="Each job is counted once. A flagged job goes to its audit rule." right={<DataBadge />}>
            <ResponsiveContainer width="100%" height={420}>
              <Sankey data={d.money_flow} nodePadding={18} nodeWidth={12} margin={{ top: 10, bottom: 10, left: 4, right: 4 }} node={<FlowNode />} link={{ stroke: "#1E4FD8", strokeOpacity: 0.16 }}>
                <Tooltip formatter={(v: any) => inr(Number(v))} />
              </Sankey>
            </ResponsiveContainer>
            <div aria-label="Legend" className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-[12.5px] text-[#2A2D33]">
              {[["source", "Billed in this ward"], ["work_type", "What it was spent on (work type)"], ["held", "Held 30 days, no flag"],
                ["failed", "Failed within 30 days"], ["review", "Needs review (one audit rule per job)"]].map(([k, label]) => (
                <span key={k} className="flex items-center gap-1.5">
                  <span className="inline-block h-3 w-3 rounded-sm" style={{ background: KIND_COLOR[k] }} />{label}
                </span>
              ))}
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-2 w-6 rounded-sm" style={{ background: "#1E4FD8", opacity: 0.25 }} />Band width = rupees billed
              </span>
            </div>
          </Section>
        </div>
        <div className="lg:col-span-2">
          <Section title="Rupees to review, by ward" hint="Darker = more to review. Click a ward to select it.">
            {geo.data ? <WardMap geo={geo.data} rows={wards.data.rows} ward={ward} onSelect={setWard} height={400} /> : <Loading />}
          </Section>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Section title="Rain drives repair spending" hint="Weekly rainfall (max of two stations) against this ward's billed work orders.">
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={d.weekly}>
              <CartesianGrid stroke="#EDEDE8" vertical={false} />
              <XAxis dataKey="week" tickFormatter={(v) => new Date(v).toLocaleDateString("en-IN", { day: "numeric", month: "short" })} fontSize={11} />
              <YAxis yAxisId="rain" fontSize={11} label={{ value: "mm", angle: -90, position: "insideLeft", fontSize: 11 }} />
              <YAxis yAxisId="inr" orientation="right" fontSize={11} tickFormatter={(v) => inr(v)} />
              <Tooltip formatter={(v: any, n: any) => (n === "Billed" ? inr(Number(v)) : `${Number(v).toFixed(0)} mm`)} />
              <Legend />
              <Bar yAxisId="rain" dataKey="rainfall_mm" name="Rainfall, mm (left axis)" fill="#9DB4EE" />
              <Line yAxisId="inr" dataKey="billed_inr" name="Billed, ₹ (right axis)" stroke="#C2410C" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Section>
        <Section title="Roads that took the most money" hint="Billed this monsoon, with repeat failures and warranty status.">
          <table className="w-full text-[13px]">
            <thead className="text-left text-[11.5px] uppercase tracking-wide text-[#454952]">
              <tr><th className="py-1">Road</th><th>Jobs</th><th>Billed</th><th>Failed</th><th>To review</th></tr>
            </thead>
            <tbody>
              {d.roads.slice(0, 8).map((r: any) => (
                <tr key={r.road_id} className="border-t border-[#EDEDE8]">
                  <td className="py-1.5 font-semibold">
                    {r.road_name} <span className="font-normal text-[#454952]">{r.road_id}</span>
                    {r.under_dlp === "Y" ? <span className="ml-2 rounded-full bg-[#EFEDFF] px-2 py-0.5 text-[11px] font-bold text-[#3A2E8C]">under warranty</span> : null}
                  </td>
                  <td>{r.jobs}</td><td>{inr(r.billed_inr)}</td><td>{r.reopened}</td><td className="font-semibold text-[#C2410C]">{r.review_inr ? inr(r.review_inr) : "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      </div>
    </div>
  );
}
