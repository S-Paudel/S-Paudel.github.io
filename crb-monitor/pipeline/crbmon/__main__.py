"""Command line:  python -m crbmon <command>

  scan      collect new images from the sources, pre-filter, analyse (scheduled job)
  analyze   run the detector on images waiting in the queue (use on a GPU machine)
  link      add one or more pasted links and analyse them straight away
  review    record a human decision (confirmed / rejected) for an analysed image
  stats     print counts
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

from .common import DEFAULT_CONFIG, Http, Settings, Store, now_iso, today
from .sources import COLLECTORS, MAPILLARY_API, resolve_link

PAGE = "https://s-paudel.github.io/crb-monitor.html"


# --------------------------------------------------------------------------
def prefilter_items(cfg: Settings, http: Http, store: Store, items: list[dict], force: bool = False) -> None:
    """Stage 2. Items passing go into the queue; failures go to rejected.json (never re-checked)."""
    pf_cfg = cfg["prefilter"]
    if not pf_cfg.get("enabled", True):
        for it in items:
            it["status"] = "queued"
            store.add(it)
        return
    from .prefilter import PalmPrefilter
    pf = PalmPrefilter(pf_cfg)
    batch: list[tuple[dict, object]] = []

    def flush():
        if not batch:
            return
        scores = pf.palm_probability([img for _, img in batch])
        for (it, _), sc in zip(batch, scores):
            it["palm_score"] = round(sc, 3)
            if pf.passes(sc) or force:
                it["status"] = "queued"
                store.add(it)
            else:
                store.reject(it["uid"], sc, "not_palm")
        batch.clear()

    for it in items:
        try:
            batch.append((it, http.image(it["thumb_url"] or it["image_url"])))
        except Exception as e:
            if force:
                it["status"] = "queued"
                store.add(it)
            else:
                store.reject(it["uid"], None, f"thumbnail_error: {e}"[:120])
            continue
        if len(batch) >= 16:
            flush()
    flush()


def refresh_mapillary_url(http: Http, item: dict) -> None:
    token = os.environ.get("MAPILLARY_TOKEN")
    if item["source"] == "mapillary" and token:
        d = http.json(f"{MAPILLARY_API}/{item['source_id']}",
                      {"access_token": token, "fields": "thumb_2048_url,thumb_256_url"}, host_key="mapillary")
        item["image_url"], item["thumb_url"] = d.get("thumb_2048_url"), d.get("thumb_256_url")


def analyze_items(cfg: Settings, http: Http, store: Store, items: list[dict], limit: int | None) -> int:
    """Stage 3. Returns how many were analysed."""
    if not items:
        return 0
    if not cfg["detector"].get("enabled", True):
        print("  detector disabled in config.toml — images stay queued")
        return 0
    try:
        from .detector import Sam3Detector
        det = Sam3Detector(cfg["detector"], cfg.base)
    except Exception as e:
        print(f"  detector unavailable ({e.__class__.__name__}: {e}) — {len(items)} image(s) stay queued.\n"
              f"  Run `python -m crbmon analyze` on a machine with the SAM3 weights (ideally a GPU).")
        return 0
    limit = min(limit or det.max_per_run, det.max_per_run)
    done = 0
    for it in items[:limit]:
        t0 = time.time()
        try:
            if it.get("url_expires"):
                refresh_mapillary_url(http, it)
            result = det.analyse(http.image(it["image_url"]))
            result["seconds"] = round(time.time() - t0, 1)
            result["analysed_at"] = now_iso()
            it["analysis"], it["status"] = result, "analyzed"
            it.pop("error", None)
            print(f"  {it['uid']}: {result['verdict']} — {result['n_palms']} palm(s), "
                  f"{result['n_cuts']} cut(s) [{result['seconds']} s]")
        except Exception as e:
            it["errors"] = it.get("errors", 0) + 1
            it["error"] = f"{e.__class__.__name__}: {e}"[:200]
            it["status"] = "error" if it["errors"] >= 3 else "queued"
            print(f"  {it['uid']}: ERROR {it['error']}")
            traceback.print_exc(limit=2)
        store.add(it)
        done += 1
    return done


# --------------------------------------------------------------------------
def cmd_scan(args, cfg: Settings) -> None:
    http, store = Http(cfg["general"]["user_agent"]), Store(cfg)
    regions = cfg.selected_regions(args.regions)
    sources = args.sources or [s for s, c in cfg["sources"].items() if c.get("enabled")]
    started, found, failed = now_iso(), Counter(), []
    for src in sources:
        for rkey, region in regions.items():
            print(f"[{src}] {region['name']}")
            try:
                cands = list(COLLECTORS[src](http, cfg, store, rkey, region))
            except Exception as e:
                print(f"  failed: {e}")
                failed.append(f"{src}:{rkey}")
                continue
            for c in cands:
                c["region"] = rkey
            beetles = [c for c in cands if c["kind"] == "beetle"]
            palms = [c for c in cands if c["kind"] != "beetle"]
            for b in beetles:
                b["status"] = "beetle_record"
                store.add(b)
            before = len(store.queued())
            prefilter_items(cfg, http, store, palms)
            passed = len(store.queued()) - before
            found[src] += len(cands)
            print(f"  {len(cands)} new · {len(beetles)} beetle record(s) · {passed} palm photo(s) queued · "
                  f"{len(palms) - passed} dropped by pre-filter")
            store.save()  # save as we go so a timeout never loses work
    analysed = 0 if args.no_analyze else analyze_items(cfg, http, store, store.queued(), args.max_analyze)
    store.log.append({"command": "scan", "started": started, "finished": now_iso(), "regions": list(regions),
                      "found": dict(found) | {s: found.get(s, 0) for s in sources}, "analysed": analysed, "failed": failed,
                      "queued_after": len(store.queued()), "window": cfg.date_window()})
    store.save()
    print(f"done: {sum(found.values())} new image(s), {analysed} analysed, {len(store.queued())} waiting")


def cmd_analyze(args, cfg: Settings) -> None:
    http, store = Http(cfg["general"]["user_agent"]), Store(cfg)
    items = [store.items[u] for u in args.uids] if args.uids else store.queued()
    n = analyze_items(cfg, http, store, items, args.max)
    store.log.append({"command": "analyze", "finished": now_iso(), "analysed": n})
    store.save()
    print(f"analysed {n}; {len(store.queued())} still waiting")


def cmd_link(args, cfg: Settings) -> None:
    http, store = Http(cfg["general"]["user_agent"]), Store(cfg)
    lines, new = [], []
    for url in args.urls:
        try:
            cands = resolve_link(http, url)
        except Exception as e:
            lines.append(f"- ❌ {url} — {e}")
            continue
        for c in cands:
            c["submitted_by"] = args.by
            c["issue"] = args.issue
            if c["uid"] in store.items and store.items[c["uid"]].get("status") == "analyzed":
                lines.append(f"- ↩️ {url} — already analysed")
                continue
            store.rejected.pop(c["uid"], None)
            new.append(c)
    prefilter_items(cfg, http, store, new, force=True)   # a person chose these, so never drop them
    queued = [store.items[c["uid"]] for c in new if c["uid"] in store.items]
    analyze_items(cfg, http, store, queued, None)
    for it in queued:
        a = it.get("analysis")
        label = {"candidate_damage": "🟠 possible CRB damage", "no_damage_detected": "🟢 no cuts found",
                 "no_palm_found": "⚪ no palm found"}.get(a["verdict"]) if a else "⏳ queued for the GPU run"
        detail = f" — {a['n_palms']} palm(s), {a['n_cuts']} V-cut(s)" if a else ""
        score = f" (palm score {it['palm_score']})" if it.get("palm_score") is not None else ""
        lines.append(f"- {label}{detail}{score}: [{it['source']}]({it['page_url']}) · "
                     f"[view on the monitor]({PAGE}#item={it['uid']})")
    store.log.append({"command": "link", "finished": now_iso(), "urls": len(args.urls), "issue": args.issue})
    store.save()
    text = "### CRB Damage Monitor results\n\n" + "\n".join(lines or ["Nothing to analyse."]) + \
           "\n\n_Automated screening only: please confirm by eye._\n"
    print(text)
    if args.summary:
        Path(args.summary).write_text(text, encoding="utf-8")


def cmd_review(args, cfg: Settings) -> None:
    store = Store(cfg)
    if args.uid not in store.items:
        sys.exit(f"unknown uid {args.uid}")
    store.items[args.uid]["review"] = {"decision": args.decision, "by": args.by, "on": today(),
                                       "note": (args.note or "")[:300]}
    store.save()
    print(f"{args.uid}: {args.decision}")


def cmd_issue(args, cfg: Settings) -> None:
    """Handle a GitHub issue opened from the web page (link submission or review)."""
    import json
    import re
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    issue = event["issue"]
    body, who, number = issue.get("body") or "", issue["user"]["login"], issue["number"]
    if "<!-- crb-monitor:review -->" in body:
        uid = re.search(r"^uid:\s*(\S+)", body, re.M)
        dec = re.search(r"^decision:\s*(confirmed|rejected|unsure)", body, re.M)
        note = re.search(r"^note:\s*(.*)$", body, re.M)
        if not (uid and dec):
            text = "Could not read the review (missing `uid:` or `decision:` line)."
        else:
            cmd_review(argparse.Namespace(uid=uid.group(1), decision=dec.group(1), by=who,
                                          note=note.group(1) if note else ""), cfg)
            text = f"Recorded **{dec.group(1)}** for `{uid.group(1)}`. Thank you!\n\n{PAGE}#item={uid.group(1)}"
        if args.summary:
            Path(args.summary).write_text(text, encoding="utf-8")
        return
    body = body.split("_Sent from")[0]
    urls = list(dict.fromkeys(u.rstrip(").,>_*") for u in re.findall(r"https?://\S+", body)))
    urls = [u for u in urls if "s-paudel.github.io" not in u.lower() and "github.com/s-paudel" not in u.lower()][:30]
    cmd_link(argparse.Namespace(urls=urls or ["(none)"], by=who, issue=number, summary=args.summary), cfg)


def cmd_stats(args, cfg: Settings) -> None:
    store = Store(cfg)
    print("status:", dict(Counter(i.get("status") for i in store.items.values())))
    print("verdict:", dict(Counter((i.get("analysis") or {}).get("verdict") for i in store.items.values()
                                   if i.get("analysis"))))
    print("source:", dict(Counter(i["source"] for i in store.items.values())))
    print("rejected by pre-filter:", len(store.rejected))


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="crbmon", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--regions", nargs="*")
    s.add_argument("--sources", nargs="*", choices=list(COLLECTORS))
    s.add_argument("--no-analyze", action="store_true", help="collect + pre-filter only")
    s.add_argument("--max-analyze", type=int)
    a = sub.add_parser("analyze")
    a.add_argument("--max", type=int)
    a.add_argument("--uids", nargs="*")
    lk = sub.add_parser("link")
    lk.add_argument("urls", nargs="+")
    lk.add_argument("--by")
    lk.add_argument("--issue", type=int)
    lk.add_argument("--summary", help="write a Markdown summary here (for the GitHub issue reply)")
    r = sub.add_parser("review")
    r.add_argument("uid")
    r.add_argument("decision", choices=["confirmed", "rejected", "unsure"])
    r.add_argument("--by")
    r.add_argument("--note")
    iss = sub.add_parser("issue", help="process a GitHub issue event (used by the workflow)")
    iss.add_argument("--event", default=os.environ.get("GITHUB_EVENT_PATH"))
    iss.add_argument("--summary")
    sub.add_parser("stats")
    args = p.parse_args(argv)
    cfg = Settings(args.config)
    {"scan": cmd_scan, "analyze": cmd_analyze, "link": cmd_link, "review": cmd_review,
     "issue": cmd_issue, "stats": cmd_stats}[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
