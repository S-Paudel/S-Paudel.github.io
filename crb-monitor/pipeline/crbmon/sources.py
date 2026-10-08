"""Collectors for each public image source, plus pasted-link resolution.

Every collector yields "candidate" dicts. Only links and metadata are kept —
images themselves are never stored, just fetched into memory for analysis.
"""
from __future__ import annotations

import hashlib
import html
import os
import re
import urllib.parse
from typing import Iterator

from .common import Http, Settings, Store, thin_key, tiles

INAT_API = "https://api.inaturalist.org/v1"
GBIF_API = "https://api.gbif.org/v1"
MAPILLARY_API = "https://graph.mapillary.com"
FLICKR_API = "https://api.flickr.com/services/rest/"
GBIF_INAT_DATASET = "50c9509d-22c7-4a22-a47d-8c48425ef4a7"
INAT_CC = "cc0,cc-by,cc-by-nc,cc-by-sa,cc-by-nd,cc-by-nc-sa,cc-by-nc-nd"
FLICKR_CC = "1,2,3,4,5,6,7,9,10"  # CC licences, "no known copyright restrictions", CC0, public domain
FLICKR_LICENSES = {"0": "all rights reserved", "1": "CC BY-NC-SA 2.0", "2": "CC BY-NC 2.0",
                   "3": "CC BY-NC-ND 2.0", "4": "CC BY 2.0", "5": "CC BY-SA 2.0", "6": "CC BY-ND 2.0",
                   "7": "no known copyright restrictions", "8": "US Government work", "9": "CC0 1.0",
                   "10": "Public Domain Mark 1.0"}


def _candidate(**kw) -> dict:
    base = dict(uid="", source="", source_id="", kind="palm", page_url="", image_url="", thumb_url="",
                lat=None, lon=None, observed_on=None, license=None, attribution=None, label=None,
                status="new")
    base.update(kw)
    if base["lat"] is not None:
        base["lat"], base["lon"] = round(float(base["lat"]), 5), round(float(base["lon"]), 5)
    return base


# ==========================================================================
# iNaturalist
# ==========================================================================
_taxon_cache: dict[str, int] = {}


def inat_taxon_id(http: Http, name: str) -> int:
    if name not in _taxon_cache:
        res = http.json(f"{INAT_API}/taxa", {"q": name, "per_page": 30})["results"]
        exact = [t for t in res if t["name"].lower() == name.lower()]
        if not exact:
            raise ValueError(f"iNaturalist taxon not found: {name}")
        _taxon_cache[name] = exact[0]["id"]
    return _taxon_cache[name]


def _inat_photo_url(url: str, size: str) -> str:
    return re.sub(r"/(square|small|medium|large|original|thumb)\.", f"/{size}.", url)


def _inat_obs_to_candidates(obs: dict, kind: str, max_photos: int) -> list[dict]:
    out = []
    coords = (obs.get("geojson") or {}).get("coordinates") or [None, None]
    taxon = (obs.get("taxon") or {}).get("name")
    for photo in (obs.get("photos") or [])[:max_photos]:
        out.append(_candidate(
            uid=f"inaturalist:{obs['id']}:{photo['id']}", source="inaturalist", source_id=str(obs["id"]),
            kind=kind, page_url=obs.get("uri") or f"https://www.inaturalist.org/observations/{obs['id']}",
            image_url=_inat_photo_url(photo["url"], "large"), thumb_url=_inat_photo_url(photo["url"], "medium"),
            lat=coords[1], lon=coords[0], observed_on=obs.get("observed_on"),
            license=photo.get("license_code") or "all rights reserved", attribution=photo.get("attribution"),
            label=taxon))
        if kind == "beetle":
            break  # one record per beetle sighting is enough
    return out


def collect_inaturalist(http: Http, cfg: Settings, store: Store, region_key: str, region: dict) -> Iterator[dict]:
    sc, f = cfg["sources"]["inaturalist"], cfg["filters"]
    d1, d2 = cfg.date_window()
    w, s, e, n = region["bbox"]
    for kind, names in (("palm", sc.get("palm_taxa", [])), ("beetle", sc.get("beetle_taxa", []))):
        if not names:
            continue
        params = {"taxon_id": ",".join(str(inat_taxon_id(http, nm)) for nm in names),
                  "swlat": s, "swlng": w, "nelat": n, "nelng": e, "d1": d1, "d2": d2,
                  "photos": "true", "per_page": 200, "order_by": "created_at", "order": "desc"}
        if f.get("cc_licensed_only"):
            params["photo_license"] = INAT_CC
        last = store.last_scan("inaturalist", region_key)
        if f.get("only_new_since_last_scan") and last:
            params["created_d1"] = last
        yielded = 0
        for page in range(1, 50):
            params["page"] = page
            results = http.json(f"{INAT_API}/observations", params)["results"]
            for obs in results:
                for c in _inat_obs_to_candidates(obs, kind, sc.get("photos_per_observation", 2)):
                    if not store.known(c["uid"]):
                        yield c
                        yielded += 1
            if len(results) < 200 or yielded >= f["max_new_per_source"]:
                break


# ==========================================================================
# GBIF
# ==========================================================================
def gbif_taxon_key(http: Http, name: str) -> int:
    key = "gbif:" + name
    if key not in _taxon_cache:
        m = http.json(f"{GBIF_API}/species/match", {"name": name})
        if not m.get("usageKey"):
            raise ValueError(f"GBIF taxon not found: {name}")
        _taxon_cache[key] = m["usageKey"]
    return _taxon_cache[key]


def gbif_thumb(occ_key, url: str, width: int = 500) -> str:
    """GBIF's image cache, keyed by the MD5 of the original image URL."""
    return f"{GBIF_API}/image/cache/{width}x/occurrence/{occ_key}/media/{hashlib.md5(url.encode()).hexdigest()}"


def _gbif_occ_to_candidates(occ: dict) -> list[dict]:
    out = []
    stills = [m for m in occ.get("media", []) if m.get("type") == "StillImage" and m.get("identifier")]
    for i, m in enumerate(stills[:2]):
        out.append(_candidate(
            uid=f"gbif:{occ['key']}:{i}", source="gbif", source_id=str(occ["key"]),
            page_url=f"https://www.gbif.org/occurrence/{occ['key']}",
            image_url=m["identifier"], thumb_url=gbif_thumb(occ["key"], m["identifier"]),
            lat=occ.get("decimalLatitude"), lon=occ.get("decimalLongitude"),
            observed_on=(occ.get("eventDate") or "")[:10] or None,
            license=m.get("license") or occ.get("license"),
            attribution=m.get("rightsHolder") or m.get("creator") or occ.get("recordedBy"),
            label=occ.get("scientificName")))
    return out


def collect_gbif(http: Http, cfg: Settings, store: Store, region_key: str, region: dict) -> Iterator[dict]:
    sc, f = cfg["sources"]["gbif"], cfg["filters"]
    d1, d2 = cfg.date_window()
    w, s, e, n = region["bbox"]
    params = {"taxonKey": [gbif_taxon_key(http, nm) for nm in sc["palm_taxa"]], "mediaType": "StillImage",
              "hasCoordinate": "true", "decimalLatitude": f"{s},{n}", "decimalLongitude": f"{w},{e}",
              "eventDate": f"{d1},{d2}", "limit": 300}
    yielded = 0
    for offset in range(0, 6000, 300):
        params["offset"] = offset
        data = http.json(f"{GBIF_API}/occurrence/search", params)
        for occ in data.get("results", []):
            if sc.get("skip_inaturalist_duplicates", True) and occ.get("datasetKey") == GBIF_INAT_DATASET:
                continue
            for c in _gbif_occ_to_candidates(occ):
                if not store.known(c["uid"]):
                    yield c
                    yielded += 1
        if data.get("endOfRecords", True) or yielded >= f["max_new_per_source"]:
            break


# ==========================================================================
# Mapillary (street-level imagery; thumbnail URLs expire, so the page refreshes them by id)
# ==========================================================================
MAPILLARY_FIELDS = "id,captured_at,computed_geometry,geometry,thumb_256_url,thumb_1024_url,thumb_2048_url,is_pano,creator"


def _mapillary_to_candidate(img: dict) -> dict:
    geom = img.get("computed_geometry") or img.get("geometry") or {"coordinates": [None, None]}
    import datetime as dt
    day = dt.datetime.fromtimestamp(img["captured_at"] / 1000, dt.timezone.utc).date().isoformat() \
        if img.get("captured_at") else None
    user = (img.get("creator") or {}).get("username")
    return _candidate(
        uid=f"mapillary:{img['id']}", source="mapillary", source_id=str(img["id"]),
        page_url=f"https://www.mapillary.com/app/?pKey={img['id']}",
        image_url=img.get("thumb_2048_url") or img.get("thumb_1024_url"),
        thumb_url=img.get("thumb_256_url") or img.get("thumb_1024_url"),
        lat=geom["coordinates"][1], lon=geom["coordinates"][0], observed_on=day,
        license="CC BY-SA 4.0", attribution=f"© {user or 'Mapillary contributor'}, Mapillary",
        label="street-level image", url_expires=True)


def collect_mapillary(http: Http, cfg: Settings, store: Store, region_key: str, region: dict) -> Iterator[dict]:
    token = os.environ.get("MAPILLARY_TOKEN")
    if not token:
        print("  mapillary: MAPILLARY_TOKEN not set — skipped")
        return
    sc, f = cfg["sources"]["mapillary"], cfg["filters"]
    d1, d2 = cfg.date_window()
    seen_cells: set[str] = set()
    yielded = 0
    for k, bbox in enumerate(tiles(region["bbox"], sc.get("tile_deg", 0.1))):
        if k >= sc.get("max_tiles_per_region", 300) or yielded >= f["max_new_per_source"]:
            break
        params = {"access_token": token, "bbox": ",".join(map(str, bbox)), "fields": MAPILLARY_FIELDS,
                  "start_captured_at": f"{d1}T00:00:00Z", "end_captured_at": f"{d2}T23:59:59Z", "limit": 2000}
        if not sc.get("include_panoramas", False):
            params["is_pano"] = "false"
        for img in http.json(f"{MAPILLARY_API}/images", params, host_key="mapillary").get("data", []):
            c = _mapillary_to_candidate(img)
            if c["lat"] is None or store.known(c["uid"]):
                continue
            cell = thin_key(c["lat"], c["lon"], sc.get("thin_metres", 150), c["observed_on"] or "")
            if cell in seen_cells:
                continue
            seen_cells.add(cell)
            yield c
            yielded += 1


# ==========================================================================
# Flickr
# ==========================================================================
def _flickr_to_candidate(p: dict) -> dict:
    return _candidate(
        uid=f"flickr:{p['id']}", source="flickr", source_id=str(p["id"]),
        page_url=f"https://www.flickr.com/photos/{p['owner']}/{p['id']}",
        image_url=p.get("url_l") or p.get("url_c") or p.get("url_z") or p.get("url_m"),
        thumb_url=p.get("url_m") or p.get("url_z"),
        lat=p.get("latitude") or None, lon=p.get("longitude") or None,
        observed_on=(p.get("datetaken") or "")[:10] or None,
        license=FLICKR_LICENSES.get(str(p.get("license")), str(p.get("license"))),
        attribution=p.get("ownername"), label=html.unescape(p.get("title") or ""))


def collect_flickr(http: Http, cfg: Settings, store: Store, region_key: str, region: dict) -> Iterator[dict]:
    key = os.environ.get("FLICKR_API_KEY")
    if not key:
        print("  flickr: FLICKR_API_KEY not set — skipped")
        return
    sc, f = cfg["sources"]["flickr"], cfg["filters"]
    d1, d2 = cfg.date_window()
    params = {"method": "flickr.photos.search", "api_key": key, "format": "json", "nojsoncallback": 1,
              "text": sc.get("text", "coconut palm"), "bbox": ",".join(map(str, region["bbox"])),
              "min_taken_date": f"{d1} 00:00:00", "max_taken_date": f"{d2} 23:59:59", "has_geo": 1,
              "content_types": 0, "sort": "date-posted-desc", "per_page": 250,
              "extras": "geo,date_taken,owner_name,license,url_m,url_z,url_c,url_l"}
    if f.get("cc_licensed_only"):
        params["license"] = FLICKR_CC
    last = store.last_scan("flickr", region_key)
    if f.get("only_new_since_last_scan") and last:
        params["min_upload_date"] = last
    yielded = 0
    for page in range(1, 20):
        params["page"] = page
        data = http.json(FLICKR_API, params)
        photos = data.get("photos", {})
        for p in photos.get("photo", []):
            c = _flickr_to_candidate(p)
            if c["image_url"] and not store.known(c["uid"]):
                yield c
                yielded += 1
        if page >= int(photos.get("pages", 1)) or yielded >= f["max_new_per_source"]:
            break


COLLECTORS = {"inaturalist": collect_inaturalist, "gbif": collect_gbif,
              "mapillary": collect_mapillary, "flickr": collect_flickr}


# ==========================================================================
# Pasted links
# ==========================================================================
def resolve_link(http: Http, url: str) -> list[dict]:
    """Turn a pasted URL (an observation/photo page, or any image or web page) into candidates."""
    url = url.strip()
    if not re.match(r"^https?://", url):
        raise ValueError(f"not a web link: {url}")

    if m := re.search(r"inaturalist\.org/observations/(\d+)", url):
        obs = http.json(f"{INAT_API}/observations/{m.group(1)}")["results"][0]
        return _inat_obs_to_candidates(obs, "palm", 4)

    if m := re.search(r"gbif\.org/occurrence/(\d+)", url):
        return _gbif_occ_to_candidates(http.json(f"{GBIF_API}/occurrence/{m.group(1)}"))

    if (m := re.search(r"mapillary\.com/.*[?&]pKey=(\d+)", url)) or \
            (m := re.search(r"mapillary\.com/.*?/(\d{6,})", url)):
        token = os.environ.get("MAPILLARY_TOKEN")
        if not token:
            raise ValueError("MAPILLARY_TOKEN is needed to resolve Mapillary links")
        img = http.json(f"{MAPILLARY_API}/{m.group(1)}", {"access_token": token, "fields": MAPILLARY_FIELDS},
                        host_key="mapillary")
        return [_mapillary_to_candidate(img)]

    if m := re.search(r"flickr\.com/photos/([^/]+)/(\d+)", url):
        key = os.environ.get("FLICKR_API_KEY")
        if not key:
            raise ValueError("FLICKR_API_KEY is needed to resolve Flickr links")
        base = {"api_key": key, "format": "json", "nojsoncallback": 1, "photo_id": m.group(2)}
        info = http.json(FLICKR_API, {**base, "method": "flickr.photos.getInfo"})["photo"]
        sizes = http.json(FLICKR_API, {**base, "method": "flickr.photos.getSizes"})["sizes"]["size"]
        by = {s["label"]: s["source"] for s in sizes}
        loc = info.get("location") or {}
        return [_flickr_to_candidate({
            "id": info["id"], "owner": info["owner"]["nsid"], "title": info["title"]["_content"],
            "url_l": by.get("Large") or by.get("Large 1600") or by.get("Medium 800") or by.get("Original"),
            "url_m": by.get("Medium") or by.get("Small 320"), "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"), "datetaken": info.get("dates", {}).get("taken"),
            "license": info.get("license"), "ownername": info["owner"].get("realname") or info["owner"]["username"]})]

    # Anything else: a direct image, or a web page with a preview image (og:image).
    r = http.get(url, host_key="link")
    uid = "link:" + hashlib.sha1(url.encode()).hexdigest()[:16]
    ctype = r.headers.get("Content-Type", "")
    if ctype.startswith("image/"):
        return [_candidate(uid=uid, source="link", source_id=url, page_url=url, image_url=url, thumb_url=url,
                           label=url.rsplit("/", 1)[-1][:80])]
    imgs = re.findall(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)',
                      r.text, flags=re.I)
    imgs += re.findall(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)',
                       r.text, flags=re.I)
    title = re.search(r"<title[^>]*>(.*?)</title>", r.text, flags=re.I | re.S)
    out = []
    for i, img in enumerate(dict.fromkeys(urllib.parse.urljoin(url, html.unescape(x)) for x in imgs)):
        out.append(_candidate(uid=f"{uid}:{i}", source="link", source_id=url, page_url=url, image_url=img,
                              thumb_url=img, label=html.unescape(title.group(1).strip())[:120] if title else url))
    if not out:
        raise ValueError("no image found at that link — paste the image's own address instead")
    return out
