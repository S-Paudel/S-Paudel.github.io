"""Settings, HTTP session and the results store."""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time
import tomllib
from pathlib import Path

import requests

PIPELINE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PIPELINE_DIR / "config.toml"


def today() -> str:
    return dt.date.today().isoformat()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
class Settings(dict):
    """config.toml plus resolved paths and the shared regions.json."""

    def __init__(self, path: Path | str = DEFAULT_CONFIG):
        path = Path(path).resolve()
        with open(path, "rb") as f:
            super().__init__(tomllib.load(f))
        self.base = path.parent
        regions_file = self.base.parent / "data" / "regions.json"
        regions = json.loads(regions_file.read_text(encoding="utf-8"))
        self.regions = {k: v for k, v in regions.items() if not k.startswith("_")}

    def path(self, rel: str) -> Path:
        return (self.base / rel).resolve()

    def selected_regions(self, override: list[str] | None = None) -> dict:
        keys = override or self["filters"]["regions"]
        missing = [k for k in keys if k not in self.regions]
        if missing:
            raise SystemExit(f"Unknown region(s) {missing}. Known: {sorted(self.regions)}")
        return {k: self.regions[k] for k in keys}

    def date_window(self) -> tuple[str, str]:
        f = self["filters"]
        return f.get("observed_from") or "1900-01-01", f.get("observed_to") or today()


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
class Http:
    """requests.Session with a polite delay and simple retries."""

    def __init__(self, user_agent: str, min_interval: float = 1.0):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = user_agent
        self.min_interval = min_interval
        self._last: dict[str, float] = {}

    def get(self, url: str, params: dict | None = None, *, host_key: str | None = None,
            timeout: int = 60, **kw) -> requests.Response:
        key = host_key or url.split("/")[2]
        for attempt in range(4):
            wait = self._last.get(key, 0) + self.min_interval - time.time()
            if wait > 0:
                time.sleep(wait)
            self._last[key] = time.time()
            try:
                r = self.s.get(url, params=params, timeout=timeout, **kw)
            except requests.RequestException:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt * 3)
                continue
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 5)
                continue
            r.raise_for_status()
            return r
        raise RuntimeError("unreachable")

    def json(self, url: str, params: dict | None = None, **kw):
        return self.get(url, params, **kw).json()

    def image(self, url: str):
        """Download an image into memory as an RGB numpy array (never written to disk)."""
        import cv2
        import numpy as np
        r = self.get(url, host_key="img:" + url.split("/")[2], timeout=90)
        arr = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
        if arr is None:
            raise ValueError(f"not a readable image: {url}")
        return cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)


# --------------------------------------------------------------------------
# Results store (JSON files committed to the repository)
# --------------------------------------------------------------------------
class Store:
    def __init__(self, settings: Settings):
        g = settings["general"]
        self.results_path = settings.path(g["results_path"])
        self.rejected_path = settings.path(g["rejected_path"])
        self.log_path = settings.path(g["log_path"])
        self.items: dict[str, dict] = {}
        self.rejected: dict[str, list] = {}
        self.log: list[dict] = []
        if self.results_path.exists():
            data = json.loads(self.results_path.read_text(encoding="utf-8"))
            self.items = {it["uid"]: it for it in data.get("items", [])}
        if self.rejected_path.exists():
            self.rejected = json.loads(self.rejected_path.read_text(encoding="utf-8"))
        if self.log_path.exists():
            self.log = json.loads(self.log_path.read_text(encoding="utf-8"))

    def known(self, uid: str) -> bool:
        return uid in self.items or uid in self.rejected

    def add(self, item: dict) -> None:
        item.setdefault("first_seen", today())
        self.items[item["uid"]] = item

    def reject(self, uid: str, score: float | None, reason: str) -> None:
        self.rejected[uid] = [today(), None if score is None else round(score, 3), reason]

    def queued(self) -> list[dict]:
        q = [it for it in self.items.values() if it.get("status") == "queued"]
        return sorted(q, key=lambda it: it.get("first_seen", ""))

    def last_scan(self, source: str, region: str) -> str | None:
        for entry in reversed(self.log):
            if entry.get("command") == "scan" and region in entry.get("regions", []) \
                    and source in entry.get("found", {}) \
                    and f"{source}:{region}" not in entry.get("failed", []):
                return entry["finished"][:10]
        return None

    def save(self) -> None:
        items = sorted(self.items.values(), key=lambda it: (it.get("first_seen", ""), it["uid"]), reverse=True)
        out = {"updated": now_iso(), "count": len(items), "items": items}
        _write_json(self.results_path, out)
        _write_json(self.rejected_path, dict(sorted(self.rejected.items())), indent=None)
        _write_json(self.log_path, self.log[-500:])


def _write_json(path: Path, data, indent: int | None = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent,
                              separators=(",", ":") if indent is None else None) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Geography helpers
# --------------------------------------------------------------------------
def tiles(bbox: list[float], step: float):
    """Split [w, s, e, n] into step×step tiles (Mapillary needs < 0.01 sq. degrees)."""
    w, s, e, n = bbox
    nx, ny = math.ceil((e - w) / step), math.ceil((n - s) / step)
    for i in range(nx):
        for j in range(ny):
            yield [round(w + i * step, 5), round(s + j * step, 5),
                   round(min(e, w + (i + 1) * step), 5), round(min(n, s + (j + 1) * step), 5)]


def thin_key(lat: float, lon: float, metres: float, day: str) -> str:
    """Grid-cell key so that only one image per cell per day is kept."""
    dlat = metres / 111_320
    dlon = metres / (111_320 * max(0.1, math.cos(math.radians(lat))))
    return f"{day}:{math.floor(lat / dlat)}:{math.floor(lon / dlon)}"
