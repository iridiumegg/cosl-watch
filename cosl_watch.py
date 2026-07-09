#!/usr/bin/env python3
"""
cosl_watch.py  --  Weekly Arkansas COSL tax-auction catalog scraper + emailer.

Scrapes the Commissioner of State Lands public auction catalog for the
counties you care about, ranks parcels by resale-opportunity heuristics,
and emails you a formatted digest. Designed to be run weekly via Windows
Task Scheduler (see setup_task.bat and README.txt).

Nate Stewart  |  nhstewart@proton.me
"""

import sys
import ssl
import smtplib
import datetime as dt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup

# =============================================================================
# CONFIG  --  edit this block only
# =============================================================================

# Counties + sale dates to watch. COSL uses 4-letter county codes.
# Format the saledate EXACTLY as it appears in the catalog URL (M/D/YYYY H:MM:SS AM).
# When this year's NWA auctions pass, update these to next year's posted dates.
WATCH = [
    {"county": "BENT", "label": "Benton",     "saledate": "8/11/2026 10:00:00 AM"},
    {"county": "WASH", "label": "Washington", "saledate": "8/11/2026 10:00:00 AM"},
    {"county": "CARR", "label": "Carroll",    "saledate": "8/12/2026 10:00:00 AM"},
    {"county": "MADI", "label": "Madison",    "saledate": "8/12/2026 10:00:00 AM"},
]

# --- Email (ProtonMail Bridge) -----------------------------------------------
# ProtonMail Bridge must be running and logged in. It exposes a LOCAL SMTP
# server, usually 127.0.0.1:1025 with STARTTLS. Copy the username + the
# bridge-generated password from the Bridge app (NOT your Proton login).
SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025
SMTP_USER = "nhstewart@proton.me"
SMTP_PASS = "PASTE_BRIDGE_PASSWORD_HERE"   # <-- Bridge app > Mailbox details
EMAIL_TO  = "nhstewart@proton.me"
EMAIL_FROM = "nhstewart@proton.me"

# --- Ranking knobs -----------------------------------------------------------
# Parcels whose opening bid (taxes owed) falls in this band are usually
# LAND-ONLY plays (cheap dirt). High owed amounts usually signal a structure.
LIKELY_IMPROVED_MIN = 8000      # >= this owed => probably has a building
BIG_ACREAGE_MIN     = 10.0      # acres >= this => raw-land $/ac play
CHEAP_LOT_MAX       = 1500      # <= this owed => cheap wholesale lot

BASE = "https://www.cosl.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# =============================================================================
# SCRAPE
# =============================================================================

def fetch_catalog(county: str, saledate: str) -> list[dict]:
    """Return a list of parcel dicts for one county/saledate catalog."""
    url = f"{BASE}/Home/CatalogView"
    params = {"county": county, "saledate": saledate}
    r = requests.get(url, params=params, headers=HEADERS, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    parcels = []
    # COSL renders the catalog as an HTML table. Rows carry the parcel data.
    # We locate the largest table and map cells positionally, with header
    # detection so this survives minor column reordering.
    table = _pick_data_table(soup)
    if table is None:
        return parcels

    rows = table.find_all("tr")
    header = [th.get_text(strip=True).lower() for th in rows[0].find_all(["th", "td"])]

    def col(row_cells, *names, default=""):
        for n in names:
            for i, h in enumerate(header):
                if n in h and i < len(row_cells):
                    return row_cells[i].get_text(" ", strip=True)
        return default

    for tr in rows[1:]:
        cells = tr.find_all("td")
        if not cells or len(cells) < 3:
            continue
        # Grab any parcel-detail link if present
        link = ""
        a = tr.find("a", href=True)
        if a:
            href = a["href"]
            link = href if href.startswith("http") else BASE + href

        rec = {
            "sale":   col(cells, "sale #", "sale"),
            "parcel": col(cells, "parcel"),
            "name":   col(cells, "name", "owner"),
            "legal":  col(cells, "legal", "description"),
            "amount": _money(col(cells, "taxes", "amount", "minimum", "bid")),
            "acres":  _acres(col(cells, "legal", "description")),
            "link":   link,
        }
        # Skip empty/junk rows
        if rec["parcel"] or rec["sale"]:
            parcels.append(rec)
    return parcels


def _pick_data_table(soup):
    tables = soup.find_all("table")
    if not tables:
        return None
    # Choose the table with the most rows (the catalog body).
    return max(tables, key=lambda t: len(t.find_all("tr")))


def _money(s: str) -> float:
    s = (s or "").replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _acres(legal: str) -> float:
    """Best-effort acreage extraction from a legal description string."""
    import re
    if not legal:
        return 0.0
    m = re.search(r"([\d]+\.?\d*)\s*(?:ac\b|acres?)", legal.lower())
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return 0.0
    return 0.0


# =============================================================================
# RANK
# =============================================================================

def score(rec: dict) -> tuple[int, str]:
    """Return (priority 0-3, tag). Higher priority = look here first."""
    amt = rec["amount"]
    ac  = rec["acres"]
    if amt >= LIKELY_IMPROVED_MIN:
        return 3, "LIKELY IMPROVED (structure?)"
    if ac >= BIG_ACREAGE_MIN:
        return 2, f"RAW ACREAGE ({ac:g} ac)"
    if 0 < amt <= CHEAP_LOT_MAX:
        return 1, "CHEAP LOT (wholesale)"
    return 0, "standard"


def rank(parcels: list[dict]) -> list[dict]:
    for p in parcels:
        pr, tag = score(p)
        p["priority"], p["tag"] = pr, tag
    # High priority first, then by amount owed descending within a tier.
    return sorted(parcels, key=lambda p: (-p["priority"], -p["amount"]))


# =============================================================================
# EMAIL
# =============================================================================

PRIORITY_COLOR = {3: "#e05a5a", 2: "#3dd6c8", 1: "#4fa3e0", 0: "#5a6280"}

def build_html(all_results: dict[str, list[dict]]) -> str:
    today = dt.date.today().strftime("%A, %B %d, %Y")
    total = sum(len(v) for v in all_results.values())
    css = """
      body{background:#0b0d11;color:#e8ecf8;font-family:Arial,Helvetica,sans-serif;
           margin:0;padding:24px;}
      h1{color:#3dd6c8;font-size:20px;margin:0 0 4px;}
      .sub{color:#5a6280;font-size:12px;margin:0 0 20px;}
      h2{color:#4fa3e0;font-size:15px;border-bottom:1px solid #1c2230;
         padding-bottom:6px;margin:26px 0 10px;}
      table{border-collapse:collapse;width:100%;font-size:12px;}
      th{text-align:left;color:#5a6280;font-weight:600;padding:6px 8px;
         border-bottom:1px solid #1c2230;}
      td{padding:6px 8px;border-bottom:1px solid #141922;vertical-align:top;}
      .amt{font-family:'DejaVu Sans Mono',monospace;color:#e8ecf8;white-space:nowrap;}
      .pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:10px;
            color:#0b0d11;font-weight:700;}
      a{color:#3dd6c8;text-decoration:none;}
      .foot{color:#5a6280;font-size:11px;margin-top:24px;border-top:1px solid #1c2230;
            padding-top:12px;}
    """
    parts = [f"<html><head><style>{css}</style></head><body>",
             "<h1>COSL Tax-Auction Watch</h1>",
             f"<p class='sub'>Weekly digest &middot; {today} &middot; {total} active parcels tracked</p>"]

    for label, parcels in all_results.items():
        if not parcels:
            parts.append(f"<h2>{label} &mdash; no parcels (redeemed out / catalog closed)</h2>")
            continue
        parts.append(f"<h2>{label} &mdash; {len(parcels)} parcels</h2>")
        parts.append("<table><tr><th>Sale#</th><th>Parcel</th><th>Opening Bid</th>"
                     "<th>Acres</th><th>Flag</th><th>Legal / Owner</th></tr>")
        for p in parcels[:60]:  # cap per county for email size
            color = PRIORITY_COLOR[p["priority"]]
            flag = (f"<span class='pill' style='background:{color}'>{p['tag']}</span>"
                    if p["priority"] > 0 else "")
            parcel_cell = (f"<a href='{p['link']}'>{p['parcel']}</a>"
                           if p["link"] else p["parcel"])
            legal = (p["legal"] or p["name"])[:70]
            parts.append(
                f"<tr><td>{p['sale']}</td><td>{parcel_cell}</td>"
                f"<td class='amt'>${p['amount']:,.0f}</td>"
                f"<td class='amt'>{p['acres'] or '&mdash;'}</td>"
                f"<td>{flag}</td><td style='color:#8891a5'>{legal}</td></tr>")
        parts.append("</table>")

    parts.append(
        "<p class='foot'>Opening bid = taxes/penalties/interest owed. 2025 taxes "
        "paid separately to county collector by Oct 15. All sales final; redemption "
        "closes 4 PM the business day before each auction, so parcels drop off week "
        "to week. Limited Warranty Deed &mdash; budget for quiet title before resale. "
        "Always verify improvements, access, flood zone &amp; liens on DataScoutPro "
        "before bidding. Source: cosl.org. This is research, not financial advice.</p>")
    parts.append("</body></html>")
    return "".join(parts)


def send_email(html: str, subject: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText("HTML email — view in an HTML-capable client.", "plain"))
    msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    # ProtonMail Bridge uses a self-signed cert on localhost; don't verify it.
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as s:
        s.ehlo()
        s.starttls(context=ctx)
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())


# =============================================================================
# MAIN
# =============================================================================

def main():
    all_results = {}
    errors = []
    for w in WATCH:
        try:
            parcels = rank(fetch_catalog(w["county"], w["saledate"]))
            all_results[w["label"]] = parcels
            print(f"[ok] {w['label']}: {len(parcels)} parcels")
        except Exception as e:
            errors.append(f"{w['label']}: {e}")
            all_results[w["label"]] = []
            print(f"[err] {w['label']}: {e}", file=sys.stderr)

    subject = f"COSL Tax-Auction Watch — {dt.date.today():%b %d}"
    if errors:
        subject += f" ({len(errors)} scrape error{'s' if len(errors) > 1 else ''})"
    html = build_html(all_results)

    # Local backup copy every run
    stamp = dt.date.today().isoformat()
    with open(f"cosl_digest_{stamp}.html", "w", encoding="utf-8") as f:
        f.write(html)

    send_email(html, subject)
    print("[ok] email sent")


if __name__ == "__main__":
    main()
