"""Next Rupee: road risk score and budget-capped allocation. Owner: budget engineer."""
import numpy as np
import pandas as pd

from .data import haversine_m

SEVERITY = {"Road cave-in": 5, "Open or broken manhole": 5, "Waterlogging": 4, "Pothole": 3,
            "Choked drain / nullah overflow": 3, "Broken paver blocks": 2, "Road related": 2, "Other": 1}
TO_WORK_TYPE = {"Road related": "Pothole", "Other": "Pothole"}
DEFAULT_WEIGHTS = {"severity": 8, "flood": 7, "traffic": 6, "facilities": 8, "accidents": 5, "repeat": 5,
                   "complaints": 6, "social": 3}
ROAD_CAUSES = ["Pothole", "Waterlogged road", "Uneven road / open chamber"]


def open_issues(t: dict, ward: str) -> pd.DataFrame:
    """Merge open complaints into issues (locality + category) and map each to its nearest road (candidate match)."""
    c = t["complaints"]
    op = c[c.status.isin(["Open", "In Progress"]) & (c.ward_code == ward)].copy()
    if op.empty:
        return pd.DataFrame()
    loc = t["localities"].set_index("locality")
    op["lat"] = op.lat.fillna(op.locality_text.map(loc.lat))
    op["lon"] = op.lon.fillna(op.locality_text.map(loc.lon))
    iss = op.groupby(["locality_text", "category_reported"]).agg(
        complaints=("complaint_id", "size"), upvotes=("upvotes", "sum"), lat=("lat", "mean"), lon=("lon", "mean"),
        first_reported=("received_at", "min"), complaint_ids=("complaint_id", lambda s: "|".join(s))).reset_index()
    iss = iss.dropna(subset=["lat"])
    roads = t["roads"][t["roads"].ward_code == ward]
    if roads.empty or iss.empty:
        return iss
    d = haversine_m(iss.lat.values[:, None], iss.lon.values[:, None], roads.mid_lat.values[None], roads.mid_lon.values[None])
    iss["road_id"] = roads.road_id.values[d.argmin(1)]
    iss["road_distance_m"] = d.min(1).round()
    iss["match_class"] = np.where(iss.road_distance_m < 800, "candidate", "unlinked")
    iss.insert(0, "issue_id", [f"ISS-{ward}-{i:03d}" for i in range(1, len(iss) + 1)])
    return iss.merge(t["roads"][["road_id", "road_name", "under_dlp", "bus_route"]], on="road_id", how="left")


def road_signals(t: dict) -> pd.DataFrame:
    rd = t["roads"].set_index("road_id")
    s = pd.DataFrame(index=rd.index)
    tr = t["traffic"].set_index("road_id")
    s["traffic"] = tr.congestion_index_0_10 / 10 * 0.6 + (rd.bus_route == "Y") * 0.4
    fac = t["facilities"]
    hosp = fac[fac.type == "Hospital"].groupby("ambulance_entry_road").size()
    sch = fac[fac.type == "School"].groupby("ambulance_entry_road").size()
    s["facilities"] = (hosp.reindex(s.index, fill_value=0) * 2 + sch.reindex(s.index, fill_value=0)).clip(upper=4) / 4
    acc = t["accidents"][t["accidents"].probable_cause.isin(ROAD_CAUSES)].groupby("road_id").size()
    s["accidents"] = acc.reindex(s.index, fill_value=0)
    reo = t["work_orders"][t["work_orders"].reopened_within_30d == "Y"].groupby("road_id").size()
    s["repeat"] = reo.reindex(s.index, fill_value=0)
    # flood: days rain crossed the nearest hotspot's threshold (2025), if a hotspot is within 700 m
    rain = t["rainfall_daily"].groupby("date").rainfall_mm.max()
    fh = t["flood_hotspots"].copy()
    fh["days_over"] = fh.flood_threshold_mm_per_day.apply(lambda th: int((rain >= th).sum()))
    d = haversine_m(rd.mid_lat.values[:, None], rd.mid_lon.values[:, None], fh.lat.values[None], fh.lon.values[None])
    near = d.min(1) < 700
    s["flood"] = np.where(near, fh.days_over.values[d.argmin(1)] * (1 + 0.3 * (fh.tide_sensitive.values[d.argmin(1)] == "Y")), 0)
    s["nearest_hotspot"] = np.where(near, fh.name.values[d.argmin(1)], "")
    s["hospitals"] = hosp.reindex(s.index, fill_value=0)
    s["schools"] = sch.reindex(s.index, fill_value=0)
    return s.reset_index()


def method_table(t: dict) -> pd.DataFrame:
    wo = t["work_orders"]
    m = wo.groupby(["work_type", "repair_method"]).agg(
        jobs=("work_order_id", "size"), median_area=("area_sqm", "median"),
        reopen_rate=("reopened_within_30d", lambda x: (x == "Y").mean()), unit=("unit", "first"),
        rate=("standard_rate_inr", "first")).reset_index()
    m["est_cost_inr"] = np.where(m.unit == "per sqm", m.rate * m.median_area, m.rate)
    m["lifetime_cost_inr"] = m.est_cost_inr * (1 + m.reopen_rate)
    return m[m.jobs >= 5]


def road_risk(t: dict, issues: pd.DataFrame, weights: dict) -> pd.DataFrame:
    if issues.empty:
        return issues
    r = issues.merge(road_signals(t), on="road_id", how="left")
    r["severity"] = r.category_reported.map(SEVERITY).fillna(1)
    r["social"] = r.locality_text.apply(
        lambda l: int(t["social_posts"].text.str.contains(str(l), case=False, regex=False).sum()))
    r["complaints_sig"] = r.complaints + r.upvotes / 10
    parts = {"severity": "severity", "flood": "flood", "traffic": "traffic", "facilities": "facilities",
             "accidents": "accidents", "repeat": "repeat", "complaints": "complaints_sig", "social": "social"}
    total_w = sum(weights.values()) or 1
    r["risk_score"] = 0.0
    for k, col in parts.items():
        mx = r[col].max()
        r[f"n_{k}"] = r[col] / mx if mx else 0
        r["risk_score"] += weights.get(k, 0) * r[f"n_{k}"]
    r["risk_score"] = (r.risk_score / total_w * 100).round(1)

    mt = method_table(t)
    def pick(row):
        wt = TO_WORK_TYPE.get(row.category_reported, row.category_reported)
        cands = mt[mt.work_type == wt]
        if cands.empty:
            return pd.Series({"method": None, "est_cost_inr": np.nan, "method_why": "no cost history"})
        high_risk = row.bus_route == "Y" or row.hospitals > 0
        best = cands.sort_values("reopen_rate").iloc[0] if high_risk else cands.sort_values("lifetime_cost_inr").iloc[0]
        why = "most durable (high-risk road)" if high_risk else "lowest lifetime cost"
        return pd.Series({"method": best.repair_method, "est_cost_inr": round(best.est_cost_inr, -2),
                          "method_why": f"{why}; re-opens {best.reopen_rate:.0%}"})
    r = pd.concat([r, r.apply(pick, axis=1)], axis=1)

    def why(row):
        bits = [f"{row.complaints} complaints"]
        if row.nearest_hotspot: bits.append(f"near {row.nearest_hotspot}")
        if row.hospitals: bits.append(f"ambulance road to {int(row.hospitals)} hospital(s)")
        if row.schools: bits.append(f"{int(row.schools)} school(s)")
        if row.bus_route == "Y": bits.append("bus route")
        if row.accidents: bits.append(f"{int(row.accidents)} road-related accidents")
        if row.social: bits.append(f"{row.social} social posts")
        return "; ".join(bits)
    r["why"] = r.apply(why, axis=1)
    return r.sort_values("risk_score", ascending=False)


def allocate(risk: pd.DataFrame, budget_inr: int) -> dict:
    sel, dfr, dlp, exc = [], [], [], []
    spent = 0
    for row in risk.to_dict("records"):
        if row.get("match_class") != "candidate":
            exc.append({**row, "reason": "no reliable road match: manual review"})
        elif pd.isna(row.get("est_cost_inr")):
            exc.append({**row, "reason": "no cost history for this work type"})
        elif row.get("under_dlp") == "Y":
            dlp.append({**row, "reason": "road under warranty: original contractor repairs at ₹0 to BMC"})
        elif spent + row["est_cost_inr"] <= budget_inr:
            sel.append(row); spent += row["est_cost_inr"]
        else:
            dfr.append({**row, "reason": "over budget after higher-risk items"})
    baseline = risk[risk.match_class == "candidate"].sort_values("complaints", ascending=False).head(len(sel))
    return {"budget_inr": budget_inr, "selected": sel, "deferred": dfr, "dlp_routed": dlp, "excluded": exc,
            "total_inr": int(spent), "unallocated_inr": int(budget_inr - spent),
            "baseline_overlap": len(set(baseline.issue_id) & {s["issue_id"] for s in sel}),
            "assumptions": ["Cost = rate card x median historical repair area for the chosen method (estimate)",
                            "One repair job per merged issue",
                            "Open complaints mapped to the nearest road segment within 800 m (candidate match)"]}
