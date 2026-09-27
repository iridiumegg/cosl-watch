#!/usr/bin/env python3
"""
build_data.py  --  Scrape the COSL catalog and write site/data.json.

Reuses the scrape + rank functions from cosl_watch.py, but sends NO email.
This is what the GitHub Actions workflow runs on a schedule to keep the
GitHub Pages dashboard (site/index.html) fresh. It can also be run by hand:

    python build_data.py

Writes <this folder>/site/data.json. Each county gets a status:
    ok      catalog scraped
    empty   sale is upcoming but the catalog returned 0 parcels
    error   the scrape raised
    passed  the sale date is over and COSL hasn't posted a newer one yet

It also pulls each county's Post Auction Sales list (parcels that didn't sell
live and are offered again online), tagged source="post" in data.json, so
the dashboard has something to show between auction seasons.

Exit code: 1 when there is at least one upcoming sale and NONE of them
returned parcels (the scraper or the site broke). The workflow then fails
visibly and skips the deploy, so the last good data stays live. When every
sale has simply passed, it exits 0 with a warning and the dashboard shows a
"sales have passed" banner instead of an empty table.
"""

import os
import sys
import json
import datetime as dt

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Chicago")   # Arkansas is Central time
except Exception:
    _TZ = None

import cosl_watch as c

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "site")
OUT_FILE = os.path.join(OUT_DIR, "data.json")


def _stamp() -> str:
    """Human-readable 'Jul 09, 2026 · 8:17 AM CT' timestamp (portable across OS)."""
    now = dt.datetime.now(_TZ) if _TZ else dt.datetime.now()
    hour = now.strftime("%I").lstrip("0") or "12"
    label = f"{now.strftime('%b %d, %Y')} · {hour}:{now.strftime('%M %p')}"
    return f"{label} CT" if _TZ else label


def build() -> dict:
    out = {"generated": _stamp(), "counties": [], "parcels": []}
    for w in c.resolve_watch():
        parcels = []
        if c.sale_passed(w["saledate"]):
            status = "passed"
            print(f"[warn] {w['label']}: sale {w['saledate']} already passed; "
                  "no newer catalog posted yet")
        else:
            try:
                parcels = c.rank(c.fetch_catalog(w["county"], w["saledate"]))
                status = "ok" if parcels else "empty"
                # Catalog empties once the auction starts; that's not a failure.
                if status == "empty" and c.sale_passed(w["saledate"],
                                                       dt.date.today() + dt.timedelta(days=1)):
                    status = "passed"
                print(f"[{'ok' if parcels else 'warn'}] {w['label']}: {len(parcels)} parcels")
            except Exception as e:        # noqa: BLE001 -- keep other counties alive
                status = "error"
                print(f"[err] {w['label']}: {e}")
        out["counties"].append({
            "label": w["label"], "code": w["county"],
            "saledate": w["saledate"], "count": len(parcels), "status": status,
        })
        _add(out, w["label"], parcels, "auction")

    # Post-auction list: parcels that didn't sell live, offered again online.
    out["post"] = []
    for w in c.WATCH:
        try:
            parcels = c.rank(c.fetch_post_auction(w["label"]))
            status = "ok"
            print(f"[ok] {w['label']} post-auction: {len(parcels)} parcels")
        except Exception as e:            # noqa: BLE001
            parcels, status = [], "error"
            print(f"[err] {w['label']} post-auction: {e}")
        out["post"].append({"label": w["label"], "count": len(parcels), "status": status})
        _add(out, w["label"], parcels, "post")
    return out


def _add(out: dict, county: str, parcels: list[dict], source: str):
    for p in parcels:
        out["parcels"].append({
            "county": county, "source": source, "sale": p["sale"],
            "parcel": p["parcel"], "name": p["name"], "legal": p["legal"],
            "amount": p["amount"], "acres": p["acres"], "priority": p["priority"],
            "tag": p["tag"], "link": p["link"],
        })


def health(data: dict) -> int:
    """Exit code for the run; prints GitHub Actions annotations."""
    counties = data["counties"]
    live = [x for x in counties if x["status"] != "passed"]
    if live and not any(x["status"] == "ok" for x in live):
        detail = ", ".join(f"{x['label']} ({x['status']})" for x in live)
        print(f"::error::No parcels scraped for any upcoming sale: {detail}. "
              "COSL may have changed the catalog page, or the site is down.")
        return 1
    post = data.get("post", [])
    if post and all(x["status"] == "error" for x in post):
        print("::warning::Post-auction list could not be read for any county. "
              "COSL may have changed that page's layout.")
    if not live:
        print("::warning::Every watched sale date has passed and COSL hasn't "
              "posted newer catalogs yet. The dashboard will show that; it "
              "picks up new sales on its own once they're posted.")
    return 0


def main():
    data = build()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[ok] wrote {OUT_FILE}: "
          f"{len(data['parcels'])} parcels across {len(data['counties'])} counties")
    sys.exit(health(data))


if __name__ == "__main__":
    main()
