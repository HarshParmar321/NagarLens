"use client";
/* eslint-disable @typescript-eslint/no-explicit-any */

import "leaflet/dist/leaflet.css";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";

import { inr, pct } from "@/lib/format";

// Ward choropleth: darker orange = more rupees to review. Click a ward to select it.
// Boundaries are the organizer's approximate (Voronoi) polygons, not official ward boundaries.
// Load with next/dynamic and ssr: false (Leaflet needs the browser).
const SCALE = ["#FDF3EC", "#F9D2B8", "#F0A070", "#D9662B", "#A8340A"];

export default function WardMap({ geo, rows, ward, onSelect, height = 460 }: {
  geo: any; rows: any[]; ward: string; onSelect: (w: string) => void; height?: number;
}) {
  const by: Record<string, any> = Object.fromEntries(rows.map((r) => [r.ward_code, r]));
  const max = Math.max(...rows.map((r) => r.total_review_inr), 1);
  const color = (v: number) => SCALE[Math.min(SCALE.length - 1, Math.floor((v / max) * SCALE.length))];
  return (
    <div>
      <MapContainer center={[19.075, 72.885]} zoom={10.5} zoomSnap={0.5} style={{ height, borderRadius: 12 }} scrollWheelZoom={false}>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution="&copy; OpenStreetMap contributors"
          opacity={0.45}
        />
        <GeoJSON
          key={ward}
          data={geo}
          style={(f: any) => {
            const code = f.properties.ward_code;
            return {
              fillColor: color(by[code]?.total_review_inr ?? 0),
              fillOpacity: 0.8,
              color: code === ward ? "#16181D" : "#FFFFFF",
              weight: code === ward ? 3.5 : 1,
            };
          }}
          onEachFeature={(f: any, layer: any) => {
            const r = by[f.properties.ward_code];
            layer.bindTooltip(
              `<b>Ward ${f.properties.ward_code}</b> · ${f.properties.ward_name}<br/>To review: <b>${inr(r?.total_review_inr)}</b> (${pct(r?.review_share)} of billed)<br/>Billed ${inr(r?.billed_inr)} of ${inr(r?.budget_inr)} budget`,
              { sticky: true },
            );
            layer.on("click", () => onSelect(f.properties.ward_code));
          }}
        />
      </MapContainer>
      <div className="mt-2 flex items-center gap-2 text-[11.5px] text-[#454952]">
        To review (billed ₹, counted once):
        {SCALE.map((c) => (
          <span key={c} className="inline-block h-3 w-7 rounded-sm" style={{ background: c }} />
        ))}
        <span>up to {inr(max)}</span>
        <span className="ml-auto">Approximate boundaries · click a ward</span>
      </div>
    </div>
  );
}
