"""Load the organizer dataset and add derived columns. Owner: trail engineer."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "raw" / "data"


def load_all() -> dict:
    t = {f.stem: pd.read_csv(f) for f in DATA.glob("*.csv")}
    wo = t["work_orders"]
    for c in ["assigned_at", "work_started_at", "completed_at"]:
        wo[c] = pd.to_datetime(wo[c])
    t["complaints"]["received_at"] = pd.to_datetime(t["complaints"]["received_at"])
    t["complaints"]["resolved_at"] = pd.to_datetime(t["complaints"]["resolved_at"])
    t["accidents"]["occurred_at"] = pd.to_datetime(t["accidents"]["occurred_at"])
    t["social_posts"]["posted_at"] = pd.to_datetime(t["social_posts"]["posted_at"])
    t["rainfall_daily"]["date"] = pd.to_datetime(t["rainfall_daily"]["date"])
    t["tides"]["date"] = pd.to_datetime(t["tides"]["date"])

    rd = t["roads"]
    rd["mid_lat"] = (rd.start_lat + rd.end_lat) / 2
    rd["mid_lon"] = (rd.start_lon + rd.end_lon) / 2

    wo = wo.merge(t["rate_card"], on="repair_method", how="left").merge(
        rd[["road_id", "road_name", "under_dlp", "bus_route", "road_type", "last_resurfaced"]], on="road_id", how="left")
    wo["expected_cost_inr"] = np.where(wo.unit == "per sqm", wo.area_sqm * wo.standard_rate_inr, wo.standard_rate_inr)
    wo["cost_ratio"] = wo.cost_inr / wo.expected_cost_inr
    wo["n_linked_complaints"] = wo.linked_complaint_ids.fillna("").apply(lambda s: len(s.split("|")) if s else 0)
    wo["hours_to_complete"] = (wo.completed_at - wo.assigned_at).dt.total_seconds() / 3600
    w = t["wards"].set_index("ward_code")
    wo["zone"] = wo.ward_code.map(w.zone)
    wo["low_lying_index"] = wo.ward_code.map(w.low_lying_index)
    t["work_orders"] = wo

    # complaint id -> work order id (exact link)
    link = wo[["work_order_id", "linked_complaint_ids"]].dropna()
    link = link.assign(complaint_id=link.linked_complaint_ids.str.split("|")).explode("complaint_id")
    t["complaints"] = t["complaints"].merge(link[["complaint_id", "work_order_id"]], on="complaint_id", how="left")

    t["wards_geo"] = json.loads((DATA / "wards.geojson").read_text(encoding="utf-8"))
    return t


def _rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [p[0] for p in geom["coordinates"]]


def ward_of_point(geo: dict, lat: float, lon: float):
    """Point-in-polygon on the organizer's approximate ward polygons (consistent with their ward_code columns)."""
    for f in geo["features"]:
        for ring in _rings(f["geometry"]):
            inside = False
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i][0], ring[i][1]
                x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
                if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-12) + x1:
                    inside = not inside
            if inside:
                return f["properties"]["ward_code"]
    return None


def haversine_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6_371_000 * 2 * np.arcsin(np.sqrt(a))
