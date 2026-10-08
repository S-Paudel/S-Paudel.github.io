"""Pre-border surveillance: new GBIF / iNaturalist records of watch-list species in the watch regions.

Grew out of Sulav Paudel's "Automated Pre-border surveillance.R" (B3 2026 ideas):
monthly records by country, month-on-month spikes (>100 %), first record in a new
country, and rapid geographic spread, plus new ideas:

  * every record is kept with the date it was FIRST SEEN, so "what is new since …" is exact
  * evidence classes, because many records in a new region are mis-identifications:
        confirmed   iNaturalist research grade (wild), or confirmed by a reviewer
        specimen    a non-iNaturalist GBIF dataset (museum, survey, lab, interception) — check
        unconfirmed iNaturalist "needs ID" / casual (wild)
        captive     iNaturalist captive / cultivated (pets, labs, interceptions)
        rejected    marked "not this species" by a reviewer
  * alerts: new record · first record in a country · first confirmed record · jump
    (> jump_km from any earlier confirmed record) · upgraded to confirmed · monthly spike ·
    record withdrawn (re-identified or deleted at the source)
  * a Markdown alert summary for the GitHub workflow to open as an issue (= e-mail)
"""
from __future__ import annotations

import datetime as dt
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from .common import Http, Settings, _write_json, now_iso, today
from .sources import (GBIF_API, GBIF_INAT_DATASET, INAT_API, area_of, gbif_area_queries,
                      gbif_taxon_key, inat_area_params, inat_taxon_id)

PAGE = "https://s-paudel.github.io/crb-surveillance.html"
EVIDENCE_RANK = {"confirmed": 0, "specimen": 1, "unconfirmed": 2, "captive": 3, "rejected": 4}


def km(a: dict, b: dict) -> float:
    r = math.radians
    dlat, dlon = r(b["lat"] - a["lat"]), r(b["lon"] - a["lon"])
    h = math.sin(dlat / 2) ** 2 + math.cos(r(a["lat"])) * math.cos(r(b["lat"])) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def evidence(rec: dict) -> str:
    rv = (rec.get("review") or {}).get("decision")
    if rv == "rejected":
        return "rejected"
    if rv == "confirmed":
        return "confirmed"
    if rec["src"] == "gbif":
        return "specimen"
    if rec.get("captive"):
        return "captive"
    return "confirmed" if rec.get("grade") == "research" else "unconfirmed"


# --------------------------------------------------------------------------
# Fetch
# --------------------------------------------------------------------------
def fetch_inat(http: Http, species: str, region: dict, cfg: dict) -> list[dict]:
    params = {"taxon_id": inat_taxon_id(http, species), **inat_area_params(region),
              "per_page": 200, "order_by": "id", "order": "asc", "id_above": 0}
    if not cfg.get("include_captive", True):
        params["captive"] = "false"
    out = []
    while len(out) < cfg.get("max_records_per_species", 10000):
        res = http.json(f"{INAT_API}/observations", params)["results"]
        for o in res:
            c = (o.get("geojson") or {}).get("coordinates") or [None, None]
            photo = (o.get("photos") or [{}])[0].get("url")
            out.append({
                "uid": f"inat:{o['id']}", "sp": species, "src": "inaturalist", "id": o["id"],
                "url": o.get("uri") or f"https://www.inaturalist.org/observations/{o['id']}",
                "area": area_of(region, place_ids=o.get("place_ids") or []),
                "lat": c[1], "lon": c[0], "date": o.get("observed_on"),
                "added": (o.get("created_at") or "")[:10] or None,
                "grade": o.get("quality_grade"), "captive": bool(o.get("captive")),
                "obscured": bool(o.get("obscured")), "place": o.get("place_guess"),
                "by": (o.get("user") or {}).get("login"), "taxon": (o.get("taxon") or {}).get("name"),
                "photo": photo.replace("/square.", "/small.") if photo else None})
        if len(res) < 200:
            break
        params["id_above"] = res[-1]["id"]
    return out


def fetch_gbif(http: Http, species: str, region: dict, cfg: dict) -> tuple[list[dict], set[int]]:
    """Non-iNaturalist GBIF records, plus the iNaturalist ids GBIF re-publishes (to mark 'also in GBIF')."""
    out, inat_ids = [], set()
    key = gbif_taxon_key(http, species)
    for q in gbif_area_queries(region):
        params = {"taxonKey": key, "occurrenceStatus": "PRESENT", "limit": 300, **q}
        for offset in range(0, cfg.get("max_records_per_species", 10000), 300):
            params["offset"] = offset
            data = http.json(f"{GBIF_API}/occurrence/search", params)
            for o in data.get("results", []):
                if o.get("datasetKey") == GBIF_INAT_DATASET:
                    ref = str(o.get("references") or "")
                    if "/observations/" in ref:
                        inat_ids.add(int(ref.rstrip("/").rsplit("/", 1)[-1]))
                    continue
                media = next((m for m in o.get("media", []) if m.get("identifier")), None)
                out.append({
                    "uid": f"gbif:{o['key']}", "sp": species, "src": "gbif", "id": o["key"],
                    "url": f"https://www.gbif.org/occurrence/{o['key']}",
                    "area": area_of(region, country=o.get("countryCode")),
                    "lat": o.get("decimalLatitude"), "lon": o.get("decimalLongitude"),
                    "date": (o.get("eventDate") or "")[:10] or None,
                    "grade": o.get("basisOfRecord"), "captive": False,
                    "place": ", ".join(x for x in (o.get("locality"), o.get("stateProvince")) if x) or None,
                    "by": o.get("recordedBy") or o.get("institutionCode"),
                    "dataset": o.get("datasetName") or o.get("datasetKey"),
                    "taxon": o.get("scientificName"),
                    "photo": media["identifier"] if media else None})
            if data.get("endOfRecords", True):
                break
    return out, inat_ids


# --------------------------------------------------------------------------
# Alerts
# --------------------------------------------------------------------------
def _month(d: str | None) -> str | None:
    return d[:7] if d and len(d) >= 7 else None


def compute_alerts(old: dict[str, dict], new: dict[str, dict], cfg: dict, settings: Settings,
                   history: list[dict]) -> list[dict]:
    run = today()
    alerts = []
    area_name = lambda k: settings.areas.get(k, {}).get("name", k or "unknown area")  # noqa: E731

    def add(kind, rec_list, text, level):
        alerts.append({"date": run, "type": kind, "level": level, "sp": rec_list[0]["sp"] if rec_list else None,
                       "area": rec_list[0].get("area") if rec_list else None,
                       "uids": [r["uid"] for r in rec_list], "text": text})

    prior = [r for r in old.values() if r.get("ev") != "rejected" and not r.get("gone")]
    for uid, r in new.items():
        if uid in old:
            # upgraded to confirmed (e.g. iNaturalist community agreed)
            if old[uid].get("ev") != "confirmed" and r["ev"] == "confirmed":
                add("upgraded", [r], f"Now confirmed: {r['sp']} in {area_name(r['area'])} ({r.get('place') or ''})", "high")
            continue
        if r["ev"] == "rejected":
            continue
        same_sp = [p for p in prior if p["sp"] == r["sp"]]
        level = {"confirmed": "high", "specimen": "medium"}.get(r["ev"], "low")
        if not any(p.get("area") == r.get("area") for p in same_sp):
            add("new_area", [r], f"FIRST record of {r['sp']} in {area_name(r['area'])} ({r['ev']})", "high")
        elif r["ev"] == "confirmed" and not any(p.get("area") == r.get("area") and p["ev"] == "confirmed" for p in same_sp):
            add("first_confirmed", [r], f"First CONFIRMED record of {r['sp']} in {area_name(r['area'])}", "high")
        else:
            add("new_record", [r], f"New {r['ev']} record of {r['sp']} in {area_name(r['area'])}"
                f"{' — ' + r['place'] if r.get('place') else ''}", level)
        conf = [p for p in same_sp if p["ev"] == "confirmed" and p.get("lat") is not None]
        if r["ev"] == "confirmed" and r.get("lat") is not None and conf:
            d = min(km(r, p) for p in conf)
            if d > cfg.get("jump_km", 100):
                add("jump", [r], f"Spread jump: confirmed {r['sp']} {d:,.0f} km from the nearest earlier confirmed "
                    f"record ({area_name(r['area'])})", "high")
        prior.append(r)

    for uid, r in old.items():
        if uid not in new and not r.get("gone"):
            add("withdrawn", [r], f"Record withdrawn or re-identified at source: {r['sp']} in {area_name(r.get('area'))}", "low")

    # Month-on-month spike (Sulav's R rule: > 100 % increase), on the last complete month
    first_of_month = dt.date.today().replace(day=1)
    last_m = (first_of_month - dt.timedelta(days=1)).strftime("%Y-%m")
    prev_m = (first_of_month - dt.timedelta(days=32)).replace(day=1).strftime("%Y-%m")
    counts = Counter((r["sp"], r.get("area"), _month(r.get("date"))) for r in new.values()
                     if r["ev"] not in ("rejected", "captive"))
    seen = {(a["type"], a.get("sp"), a.get("area"), a.get("month")) for a in history}
    for (sp, area, m), n in list(counts.items()):
        if m != last_m:
            continue
        p = counts.get((sp, area, prev_m), 0)
        if n >= cfg.get("spike_min_records", 3) and n > 2 * p and ("spike", sp, area, m) not in seen:
            alerts.append({"date": run, "type": "spike", "level": "medium", "sp": sp, "area": area, "month": m,
                           "uids": [], "text": f"Monthly spike: {n} records of {sp} in {area_name(area)} in {m} "
                                               f"(previous month {p})"})
    return alerts


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------
def run(settings: Settings, http: Http, alert_file: str | None = None) -> dict:
    cfg = settings["surveillance"]
    path = settings.path(cfg["path"])
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    old = {r["uid"]: r for r in data.get("records", [])}
    baseline = not old and not data.get("scans")
    regions = [settings.region(k) for k in cfg["regions"]]
    merged = {"regions": cfg["regions"], "areas": sorted({a["key"] for g in regions for a in g["areas"]})}

    fetched: dict[str, dict] = {}
    complete = True
    for sp in cfg["species"]:
        for region in regions:
            print(f"[surveillance] {sp} · {region['name']}")
            try:
                inat = fetch_inat(http, sp, region, cfg)
                gbif, inat_in_gbif = fetch_gbif(http, sp, region, cfg)
            except Exception as e:  # keep earlier records untouched if a source is down
                print(f"  failed: {e}")
                complete = False
                continue
            for r in inat:
                r["in_gbif"] = r["id"] in inat_in_gbif
            for r in inat + gbif:
                fetched[r["uid"]] = r
            print(f"  iNaturalist {len(inat)} · GBIF (other datasets) {len(gbif)}")

    new: dict[str, dict] = {}
    for uid, r in fetched.items():
        prev = old.get(uid, {})
        r["first_seen"] = prev.get("first_seen") or ("baseline" if baseline else today())
        if prev.get("review"):
            r["review"] = prev["review"]
        r["ev"] = evidence(r)
        new[uid] = r
    for uid, r in old.items():          # keep everything ever seen; mark what has disappeared
        if uid not in new:
            r = dict(r)
            if complete:
                r["gone"] = r.get("gone") or today()
            new[uid] = r

    history = data.get("alerts", [])
    current = {uid: new[uid] for uid in fetched}
    alerts = [] if baseline else compute_alerts(old, current, cfg, settings, history)
    if not complete:
        alerts = [a for a in alerts if a["type"] != "withdrawn"]
    species_meta = []
    for sp in cfg["species"]:
        try:
            species_meta.append({"name": sp, "inat_id": inat_taxon_id(http, sp), "gbif_key": gbif_taxon_key(http, sp)})
        except Exception:
            species_meta.append({"name": sp})
    out = {
        "updated": now_iso(), "baseline": data.get("baseline") or today(), "species": species_meta, **merged,
        "records": sorted(new.values(), key=lambda r: (r.get("date") or "", r["uid"]), reverse=True),
        "alerts": (alerts + history)[:500],
        "scans": ([{"date": now_iso(), "fetched": len(fetched), "new": sum(1 for r in new.values() if r.get("first_seen") == today()),
                    "alerts": len(alerts), "complete": complete}] + data.get("scans", []))[:400],
    }
    _write_json(path, out)
    print(f"done: {len(fetched)} records, {len(alerts)} alert(s){' (baseline run — no alerts)' if baseline else ''}")

    if alert_file and alerts:
        Path(alert_file).write_text(alert_markdown(alerts, settings), encoding="utf-8")
    return out


def alert_markdown(alerts: list[dict], settings: Settings) -> str:
    icon = {"high": "🔴", "medium": "🟠", "low": "⚪"}
    lines = [f"**{len(alerts)} new surveillance alert(s)** from the CRB pre-border monitor ({today()}).", ""]
    for a in sorted(alerts, key=lambda a: {"high": 0, "medium": 1, "low": 2}[a["level"]]):
        links = " ".join(f"[record]({_url(u)})" for u in a["uids"][:3])
        lines.append(f"- {icon[a['level']]} {a['text']} {links}")
    lines += ["", f"Open the dashboard: {PAGE}", "",
              "_Records come from GBIF and iNaturalist and may be mis-identified. Check the photo before acting._"]
    return "\n".join(lines) + "\n"


def alert_title(alerts: list[dict], settings: Settings) -> str:
    areas = sorted({settings.areas.get(a.get("area"), {}).get("name", "") for a in alerts} - {""})
    top = "FIRST record" if any(a["type"] == "new_area" for a in alerts) else f"{len(alerts)} new alert(s)"
    return f"[CRB alert] {top} — {', '.join(areas[:4])}{'…' if len(areas) > 4 else ''}"


def _url(uid: str) -> str:
    src, i = uid.split(":", 1)
    return f"https://www.inaturalist.org/observations/{i}" if src == "inat" else f"https://www.gbif.org/occurrence/{i}"


def review(settings: Settings, uid: str, decision: str, by: str | None, note: str | None) -> bool:
    path = settings.path(settings["surveillance"]["path"])
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    for r in data.get("records", []):
        if r["uid"] == uid:
            r["review"] = {"decision": decision, "by": by, "on": today(), "note": (note or "")[:300]}
            r["ev"] = evidence(r)
            _write_json(path, data)
            return True
    return False
