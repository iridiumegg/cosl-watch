#!/usr/bin/env python3
"""
build_data.py  --  Scrape the COSL catalog and write site/data.json.

Reuses the scrape + rank functions from cosl_watch.py, but sends NO email.
This is what the GitHub Actions workflow runs on a schedule to keep the
GitHub Pages dashboard (site/index.html) fresh. It can also be run by hand:

    python build_data.py

Writes <this folder>/site/data.json. Exits 0 even if some counties fail to
scrape (their section just shows zero parcels), so a single flaky county
never blocks the whole site update.
"""

import os
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
    for w in c.WATCH:
        try:
            parcels = c.rank(c.fetch_catalog(w["county"], w["saledate"]))
            print(f"[ok] {w['label']}: {len(parcels)} parcels")
        except Exception as e:            # noqa: BLE001 -- keep other counties alive
            parcels = []
            print(f"[err] {w['label']}: {e}")
        out["counties"].append({
            "label": w["label"], "code": w["county"],
            "saledate": w["saledate"], "count": len(parcels),
        })
        for p in parcels:
            out["parcels"].append({
                "county": w["label"], "sale": p["sale"], "parcel": p["parcel"],
                "name": p["name"], "legal": p["legal"], "amount": p["amount"],
                "acres": p["acres"], "priority": p["priority"], "tag": p["tag"],
                "link": p["link"],
            })
    return out


def main():
    data = build()
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[ok] wrote {OUT_FILE}: "
          f"{len(data['parcels'])} parcels across {len(data['counties'])} counties")


if __name__ == "__main__":
    main()
