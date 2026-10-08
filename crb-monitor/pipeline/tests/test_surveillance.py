"""Surveillance logic on real GBIF / iNaturalist CRB records captured on 9 Oct 2026 (no network needed)."""
import copy
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from crbmon import surveillance  # noqa: E402
from crbmon.common import Settings  # noqa: E402

FIXTURE = json.loads((HERE / "fixtures" / "crb_americas_2026-10-09.json").read_text(encoding="utf-8"))


class FakeHttp:
    """Answers the iNaturalist / GBIF calls the surveillance module makes, from the fixture."""

    def __init__(self, fx, settings):
        self.fx, self.s = fx, settings

    def _region(self, params):
        for key in self.s["surveillance"]["regions"]:
            reg = self.s.region(key)
            places = ",".join(str(a["inat_place"]) for a in reg["areas"])
            if params.get("place_id") == places:
                return key
            countries = params.get("country")
            if countries is not None:
                want = countries if isinstance(countries, list) else [countries]
                if sorted(want) == sorted(a["country"] for a in reg["areas"]):
                    return key
        raise AssertionError(f"unexpected query {params}")

    def json(self, url, params=None, **kw):
        params = params or {}
        if url.endswith("/taxa"):
            return {"results": [{"id": 320058, "name": params["q"]}]}
        if url.endswith("/species/match"):
            return {"usageKey": 4995642}
        if url.endswith("/observations"):
            rows = [o for o in self.fx["inat"][self._region(params)] if o["id"] > params.get("id_above", 0)]
            return {"results": sorted(rows, key=lambda o: o["id"])[:200]}
        if url.endswith("/occurrence/search"):
            rows = self.fx["gbif"][self._region(params)]
            return {"results": rows[params["offset"]:params["offset"] + 300], "endOfRecords": True}
        raise AssertionError(url)


@pytest.fixture
def settings(tmp_path):
    s = Settings()
    s["surveillance"] = dict(s["surveillance"], path=str(tmp_path / "surveillance.json"))
    return s


def run(settings, fx, alert_file=None):
    return surveillance.run(settings, FakeHttp(fx, settings), alert_file)


def test_baseline_has_no_alerts_and_classifies_evidence(settings):
    out = run(settings, FIXTURE)
    recs = {r["uid"]: r for r in out["records"]}
    assert out["alerts"] == []
    assert len(recs) == 64 + 5 + 3 + 21 + 1          # iNat + GBIF non-iNat datasets
    assert recs["inat:405688598"]["ev"] == "confirmed" and recs["inat:405688598"]["area"] == "MX"
    assert recs["inat:405688598"]["in_gbif"] is False and recs["inat:402513617"]["in_gbif"] is True
    assert recs["inat:133290892"]["ev"] == "captive" and recs["inat:133290892"]["area"] == "EC"
    assert recs["inat:403895568"]["ev"] == "unconfirmed" and recs["inat:403895568"]["area"] == "CO"
    assert recs["gbif:3306195993"]["ev"] == "specimen"   # 2014 Manzanillo customs interception
    assert recs["inat:10703221"]["area"] == "US48"
    assert all(r["first_seen"] == "baseline" for r in recs.values())


def test_new_records_raise_the_right_alerts(settings, tmp_path):
    before = copy.deepcopy(FIXTURE)
    sa = before["inat"]["south_america"]
    before["inat"]["south_america"] = [o for o in sa if o["id"] not in (109951346, 403895568)]  # no Colombia yet
    mx = before["inat"]["mexico_central_america"]
    before["inat"]["mexico_central_america"] = [o for o in mx if o["id"] != 405688598]          # newest Jalisco record
    for o in mx:
        if o["id"] == 402513617:
            o["quality_grade"] = "needs_id"                                                     # later upgraded
    before["inat"]["us_contiguous"].append({**before["inat"]["us_contiguous"][0], "id": 1})     # later withdrawn
    run(settings, before)

    after = copy.deepcopy(FIXTURE)
    jumper = copy.deepcopy(next(o for o in after["inat"]["mexico_central_america"] if o["id"] == 405688598))
    jumper.update(id=999999999, geojson={"type": "Point", "coordinates": [-97.0, 20.9]})        # Veracruz, ~850 km
    after["inat"]["mexico_central_america"].append(jumper)
    alert_md = tmp_path / "alert.md"
    out = run(settings, after, str(alert_md))
    types = sorted(a["type"] for a in out["alerts"])
    print(types)
    assert types.count("new_area") == 1                      # first record in Colombia (two records, one alert)
    assert "upgraded" in types and "withdrawn" in types and "jump" in types
    assert any(a["type"] == "new_record" and "inat:405688598" in a["uids"] for a in out["alerts"])
    assert any(a["type"] == "new_record" and "inat:403895568" in a["uids"] for a in out["alerts"])
    assert "[record](https://www.inaturalist.org/observations/" in alert_md.read_text(encoding="utf-8")
    title = surveillance.alert_title(out["alerts"], settings)
    assert title.startswith("[CRB alert] FIRST record") and "Colombia" in title


def test_review_overrides_evidence(settings):
    run(settings, FIXTURE)
    assert surveillance.review(settings, "inat:403895568", "rejected", "S-Paudel", "Strategus, not Oryctes")
    data = json.loads(Path(settings["surveillance"]["path"]).read_text(encoding="utf-8"))
    rec = next(r for r in data["records"] if r["uid"] == "inat:403895568")
    assert rec["ev"] == "rejected" and rec["review"]["note"].startswith("Strategus")
    out = run(settings, FIXTURE)                              # a later scan keeps the review
    assert next(r for r in out["records"] if r["uid"] == "inat:403895568")["ev"] == "rejected"
