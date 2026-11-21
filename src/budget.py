"""Next Rupee: map open complaints to roads, score road risk, allocate a budget. Owner: budget engineer.

Pipeline: open complaints -> ward fill (GPS polygon / gazetteer) -> triage (cached Claude, else rules) ->
road match per complaint (GPS = high confidence, road named in text = candidate, else unlinked) ->
issues grouped by (road, category) -> citywide-normalised risk score -> budget- and crew-capped allocation.
Nothing is dropped silently: every complaint that does not become a fundable issue is returned with a reason.
"""
import numpy as np
import pandas as pd

from . import ai
from .data import haversine_m, ward_of_point

SEVERITY = {"Road cave-in": 5, "Open or broken manhole": 5, "Waterlogging": 4, "Pothole": 3,
            "Choked drain / nullah overflow": 3, "Broken paver blocks": 2}
DEFAULT_WEIGHTS = {"severity": 8, "flood": 7, "traffic": 6, "facilities": 8, "accidents": 5, "repeat": 5,
                   "complaints": 6, "social": 3}
ROAD_CAUSES = ["Pothole", "Waterlogged road", "Uneven road / open chamber"]
PLAN_DAYS = 7  # crew capacity window: engineering_crews x PLAN_DAYS jobs


def _gazetteer(t):
    """lower-case name or alias -> (locality, ward, lat, lon)."""
    g = {}
    for r in t["localities"].itertuples():
        for name in [r.locality, *(str(r.aliases).split(";") if isinstance(r.aliases, str) else [])]:
            if name and name.strip():
                g[name.strip().lower()] = (r.locality, r.ward_code, r.lat, r.lon)
    return g


def _locality(gaz, text):
    if not isinstance(text, str) or not text.strip():
        return None
    k = text.strip().lower()
    if k in gaz:
        return gaz[k]
    pref = {v for n, v in gaz.items() if n.startswith(k) or k.startswith(n)}
    return next(iter(pref)) if len(pref) == 1 else None


def map_open_complaints(t: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every open/in-progress complaint -> (placed complaints, excluded complaints with a reason)."""
    c = t["complaints"]
    op = c[c.status.isin(["Open", "In Progress"])].copy()
    gaz = _gazetteer(t)
    loc = op.locality_text.apply(lambda s: _locality(gaz, s))
    op["loc_name"] = loc.apply(lambda v: v[0] if v else None)
    op["loc_lat"] = loc.apply(lambda v: v[2] if v else np.nan)
    op["loc_lon"] = loc.apply(lambda v: v[3] if v else np.nan)
    # 1. ward: given, else GPS polygon, else gazetteer
    no_w = op.ward_code.isna()
    op.loc[no_w & op.lat.notna(), "ward_code"] = op[no_w & op.lat.notna()].apply(
        lambda r: ward_of_point(t["wards_geo"], r.lat, r.lon), axis=1)
    no_w = op.ward_code.isna()
    op.loc[no_w, "ward_code"] = loc[no_w].apply(lambda v: v[1] if v else None)
    # 2. triage: cached model output if present, else rules (no model call during page load)
    tri = op.apply(lambda r: ai.triage(str(r.description), [], r.category_reported, r.language, allow_call=False), axis=1)
    op["category"] = tri.apply(lambda d: d["category"])
    op["triage_source"] = tri.apply(lambda d: d["source"])
    op["is_noise"] = tri.apply(lambda d: bool(d.get("is_noise")))
    # 3. road match per complaint
    roads = t["roads"]
    names = sorted(roads.road_name.unique(), key=len, reverse=True)
    rows = []
    for r in op.itertuples():
        base = dict(complaint_id=r.complaint_id, ward_code=r.ward_code, category=r.category, upvotes=r.upvotes,
                    received_at=r.received_at, locality=r.loc_name or r.locality_text, triage_source=r.triage_source,
                    description=r.description)
        if r.ward_code is None or (isinstance(r.ward_code, float) and np.isnan(r.ward_code)):
            rows.append({**base, "reason": "ward unknown: no GPS and locality not in gazetteer"}); continue
        if r.is_noise or r.category not in SEVERITY:
            rows.append({**base, "reason": "not a road-repair issue (triage)"}); continue
        wr = roads[roads.ward_code == r.ward_code]
        if pd.notna(r.lat):
            d = haversine_m(r.lat, r.lon, wr.mid_lat.values, wr.mid_lon.values)
            i = int(d.argmin())
            rows.append({**base, "road_id": wr.road_id.iloc[i], "road_ids": [wr.road_id.iloc[i]], "lat": r.lat, "lon": r.lon,
                         "match_class": "gps", "match_note": f"GPS, {d[i]:.0f} m from segment midpoint"}); continue
        desc = str(r.description).lower()
        named = next((n for n in names if n.lower() in desc and n in set(wr.road_name)), None)
        if named:
            segs = wr[wr.road_name == named]
            if pd.notna(r.loc_lat):
                d = haversine_m(r.loc_lat, r.loc_lon, segs.mid_lat.values, segs.mid_lon.values)
                i = int(d.argmin())
            else:
                i = 0
            rows.append({**base, "road_id": segs.road_id.iloc[i], "road_ids": list(segs.road_id),
                         "lat": segs.mid_lat.iloc[i], "lon": segs.mid_lon.iloc[i], "match_class": "road named",
                         "match_note": f"road named in text; {len(segs)} segment(s), exact segment uncertain"}); continue
        rows.append({**base, "reason": "no GPS and no road named: needs a field check"})
    df = pd.DataFrame(rows)
    placed = df[df.get("road_id").notna()] if "road_id" in df else df.iloc[0:0]
    excluded = df[df.road_id.isna()] if "road_id" in df else df
    return placed.reset_index(drop=True), excluded.reset_index(drop=True)


def open_issues(t: dict, ward: str) -> pd.DataFrame:
    """Placed open complaints in a ward, merged into issues by (road segment, category)."""
    if "_open_map" not in t:
        t["_open_map"] = map_open_complaints(t)
    placed, _ = t["_open_map"]
    p = placed[placed.ward_code == ward]
    if p.empty:
        return pd.DataFrame()
    iss = p.groupby(["road_id", "category"]).agg(
        complaints=("complaint_id", "size"), upvotes=("upvotes", "sum"), lat=("lat", "mean"), lon=("lon", "mean"),
        first_reported=("received_at", "min"), complaint_ids=("complaint_id", lambda s: "|".join(s)),
        locality_text=("locality", lambda s: s.mode().iloc[0] if len(s.mode()) else ""),
        road_ids=("road_ids", lambda s: sorted({x for l in s for x in l})),
        match_class=("match_class", lambda s: "gps" if (s == "gps").any() else "road named")).reset_index()
    iss = iss.rename(columns={"category": "category_reported"})
    iss.insert(0, "issue_id", [f"ISS-{ward}-{i:03d}" for i in range(1, len(iss) + 1)])
    return iss.merge(t["roads"][["road_id", "road_name", "under_dlp", "bus_route"]], on="road_id", how="left")


def excluded_complaints(t: dict, ward: str) -> pd.DataFrame:
    if "_open_map" not in t:
        t["_open_map"] = map_open_complaints(t)
    _, exc = t["_open_map"]
    return exc[exc.ward_code == ward]


def road_signals(t: dict) -> pd.DataFrame:
    if "_signals" in t:
        return t["_signals"]
    rd = t["roads"].set_index("road_id")
    s = pd.DataFrame(index=rd.index)
    tr = t["traffic"].set_index("road_id")
    s["traffic"] = tr.congestion_index_0_10.reindex(s.index).fillna(0) / 10 * 0.6 + (rd.bus_route == "Y") * 0.4
    fac = t["facilities"]
    hosp = fac[fac.type == "Hospital"].groupby("ambulance_entry_road").size()
    sch = fac[fac.type == "School"].groupby("ambulance_entry_road").size()
    s["facilities"] = (hosp.reindex(s.index, fill_value=0) * 2 + sch.reindex(s.index, fill_value=0)).clip(upper=4) / 4
    acc = t["accidents"][t["accidents"].probable_cause.isin(ROAD_CAUSES)].groupby("road_id").size()
    s["accidents"] = acc.reindex(s.index, fill_value=0)
    reo = t["work_orders"][t["work_orders"].reopened_within_30d == "Y"].groupby("road_id").size()
    s["repeat"] = reo.reindex(s.index, fill_value=0)
    rain = t["rainfall_daily"].groupby("date").rainfall_mm.max()
    fh = t["flood_hotspots"].copy()
    fh["days_over"] = fh.flood_threshold_mm_per_day.apply(lambda th: int((rain >= th).sum()))
    d = haversine_m(rd.mid_lat.values[:, None], rd.mid_lon.values[:, None], fh.lat.values[None], fh.lon.values[None])
    near = d.min(1) < 700
    j = d.argmin(1)
    s["flood"] = np.where(near, fh.days_over.values[j] * (1 + 0.3 * (fh.tide_sensitive.values[j] == "Y")), 0)
    s["nearest_hotspot"] = np.where(near, fh.name.values[j], "")
    s["hospitals"] = hosp.reindex(s.index, fill_value=0)
    s["schools"] = sch.reindex(s.index, fill_value=0)
    t["_signals"] = s
    return s


def method_table(t: dict) -> pd.DataFrame:
    wo = t["work_orders"]
    m = wo.groupby(["work_type", "repair_method"]).agg(
        jobs=("work_order_id", "size"), median_area=("area_sqm", "median"),
        reopen_rate=("reopened_within_30d", lambda x: (x == "Y").mean()), unit=("unit", "first"),
        rate=("standard_rate_inr", "first")).reset_index()
    m["est_cost_inr"] = np.where(m.unit == "per sqm", m.rate * m.median_area, m.rate)
    m["lifetime_cost_inr"] = m.est_cost_inr * (1 + m.reopen_rate)
    return m[m.jobs >= 5]


# Citywide normalisers, so a score of 60 means the same thing in every ward.
SCALE = {"severity": 5, "complaints": 10, "social": 20}


def road_risk(t: dict, issues: pd.DataFrame, weights: dict) -> pd.DataFrame:
    if issues.empty:
        return issues
    sig = road_signals(t)
    cols = ["traffic", "facilities", "accidents", "repeat", "flood", "hospitals", "schools"]
    avg = issues.road_ids.apply(lambda ids: sig.loc[ids, cols].mean())  # average over all candidate segments
    r = pd.concat([issues.reset_index(drop=True), avg.reset_index(drop=True)], axis=1)
    r["nearest_hotspot"] = issues.road_id.map(sig.nearest_hotspot).values
    r["severity"] = r.category_reported.map(SEVERITY).fillna(1)
    posts = t["social_posts"].text.str.lower()
    r["social"] = r.locality_text.apply(lambda l: int(posts.str.contains(str(l).lower(), regex=False).sum()) if l else 0)
    r["complaints_sig"] = r.complaints + r.upvotes / 10
    maxes = {k: (sig[k].max() or 1) for k in ["traffic", "facilities", "accidents", "repeat", "flood"]}
    norm = {"severity": r.severity / SCALE["severity"], "complaints": (r.complaints_sig / SCALE["complaints"]).clip(upper=1),
            "social": (r.social / SCALE["social"]).clip(upper=1), **{k: r[k] / maxes[k] for k in maxes}}
    total_w = sum(weights.values()) or 1
    r["risk_score"] = (sum(weights.get(k, 0) * norm[k] for k in norm) / total_w * 100).round(1)
    for k in norm:
        r[f"n_{k}"] = norm[k]

    mt = method_table(t)

    def pick(row):
        cands = mt[mt.work_type == row.category_reported]
        if cands.empty:
            return pd.Series({"method": None, "est_cost_inr": np.nan, "method_why": "no cost history"})
        high_risk = row.bus_route == "Y" or row.hospitals > 0
        best = cands.sort_values("reopen_rate").iloc[0] if high_risk else cands.sort_values("lifetime_cost_inr").iloc[0]
        why = "most durable (high-risk road)" if high_risk else "lowest lifetime cost"
        return pd.Series({"method": best.repair_method, "est_cost_inr": round(best.est_cost_inr, -2),
                          "method_why": f"{why}; re-opens {best.reopen_rate:.0%}"})
    r = pd.concat([r, r.apply(pick, axis=1)], axis=1)

    def why(row):
        bits = [f"{row.complaints} complaint(s)"]
        if row.nearest_hotspot: bits.append(f"flood hotspot: {row.nearest_hotspot}")
        if row.hospitals: bits.append("hospital ambulance road")
        if round(row.schools): bits.append(f"{round(row.schools)} school(s)")
        if row.bus_route == "Y": bits.append("bus route")
        if round(row.accidents): bits.append(f"{round(row.accidents)} road accidents")
        if round(row["repeat"]): bits.append(f"{round(row['repeat'])} failed fixes")
        if row.social: bits.append(f"{row.social} social posts")
        return "; ".join(bits)
    r["why"] = r.apply(why, axis=1)
    return r.sort_values("risk_score", ascending=False)


def default_budget(t: dict, ward: str, findings: pd.DataFrame) -> tuple[int, str]:
    """Remaining ward budget; for overspent wards, the money recoverable from flagged jobs."""
    w = t["wards"].set_index("ward_code").loc[ward]
    remaining = int(w.monsoon_repair_budget_inr_2025 - t["work_orders"].query("ward_code == @ward").cost_inr.sum())
    if remaining > 0:
        return remaining, "remaining 2025 ward budget"
    f = findings[(findings.ward_code == ward) & findings.rule_id.isin(["dlp_paid_by_bmc", "duplicate_bill"])]
    rec = int(f.drop_duplicates("work_order_id").amount_at_risk_inr.sum())
    return rec, f"ward overspent by ₹{-remaining:,}; plan uses money recoverable from warranty and duplicate bills"


def allocate(risk: pd.DataFrame, budget_inr: int, crew_jobs: int | None = None) -> dict:
    sel, dfr, dlp, exc = [], [], [], []
    spent = 0
    for row in risk.to_dict("records"):
        if pd.isna(row.get("est_cost_inr")):
            exc.append({**row, "reason": "no cost history for this work type"})
        elif row.get("under_dlp") == "Y":
            dlp.append({**row, "reason": "road under warranty: original contractor repairs at ₹0 to BMC"})
        elif crew_jobs is not None and len(sel) >= crew_jobs:
            dfr.append({**row, "reason": f"crew capacity reached ({crew_jobs} jobs in {PLAN_DAYS} days)"})
        elif spent + row["est_cost_inr"] <= budget_inr:
            sel.append(row); spent += row["est_cost_inr"]
        else:
            dfr.append({**row, "reason": "over budget after higher-risk items"})
    eligible = risk[risk.est_cost_inr.notna() & (risk.under_dlp != "Y")] if len(risk) else risk
    baseline = eligible.sort_values(["complaints", "upvotes"], ascending=False).head(len(sel)) if len(risk) else eligible
    return {"budget_inr": budget_inr, "selected": sel, "deferred": dfr, "dlp_routed": dlp, "excluded": exc,
            "total_inr": int(spent), "unallocated_inr": int(budget_inr - spent),
            "baseline_overlap": len(set(baseline.issue_id) & {s["issue_id"] for s in sel}) if len(risk) else 0,
            "assumptions": ["Cost = rate card x median historical repair area for the chosen method (estimate)",
                            "One repair job per issue (road segment + problem)",
                            "Road match: GPS to nearest segment; otherwise the road named in the complaint (segment uncertain)",
                            f"Crew capacity: ward crews x {PLAN_DAYS} days, one job per crew-day"]}
