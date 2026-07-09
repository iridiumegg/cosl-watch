COSL TAX-AUCTION WATCH  —  weekly scraper + email digest
=========================================================
Scrapes the Arkansas Commissioner of State Lands public auction catalog
(cosl.org) for the counties you pick, ranks parcels by resale opportunity,
and emails you a dark-themed HTML digest every Monday at 8 AM.

Default counties: Benton, Washington (8/11 sale) + Carroll, Madison (8/12 sale).


ONE-TIME SETUP  (about 5 minutes)
---------------------------------
1. Install Python 3.10+ from python.org. During install, CHECK
   "Add python.exe to PATH".

2. Open a terminal in this folder and install the two libraries:

       pip install requests beautifulsoup4

3. Make sure ProtonMail Bridge is installed, running, and logged in.
   Open Bridge > your account > "Mailbox details" and copy:
       - the SMTP username (your address)
       - the Bridge-generated password (NOT your normal Proton password)
       - the SMTP port (usually 1025)

4. Open cosl_watch.py and edit the CONFIG block at the top:
       SMTP_PASS = "..."      <- paste the Bridge password
       SMTP_PORT = 1025       <- match what Bridge shows
   (EMAIL_TO / SMTP_USER are already set to nhstewart@proton.me.)

5. TEST IT ONCE by hand before scheduling:

       python cosl_watch.py

   You should see one "[ok] <county>: N parcels" line per county and
   "[ok] email sent", plus an email in your inbox and a
   cosl_digest_YYYY-MM-DD.html backup in this folder.

   >> If a county shows "0 parcels" but the catalog isn't empty, COSL
      tweaked their table markup. Open the saved .html, or tell Claude,
      and the parser's column mapping in fetch_catalog() gets a quick fix.

6. SCHEDULE IT: right-click setup_task.bat > "Run as administrator".
   That registers task "COSL_Watch" for every Monday 8:00 AM.


HANDY COMMANDS
--------------
   Run now:     schtasks /Run    /TN "COSL_Watch"
   Check it:    schtasks /Query  /TN "COSL_Watch"
   Remove it:   schtasks /Delete /TN "COSL_Watch" /F

Output log each run:  cosl_watch.log  (in this folder)


LIVING WEB DASHBOARD  (GitHub Pages)
------------------------------------
Besides the weekly email, this repo publishes a live, filterable dashboard
you can open in any browser. It updates itself in the cloud via GitHub
Actions, so it stays fresh even when this PC is off.

How it fits together:
   build_data.py            scrapes the catalog and writes site/data.json
                            (same scraper as the email; sends NO email)
   site/index.html          the dashboard; loads data.json in the browser
   .github/workflows/       runs build_data.py daily (~8 AM Central) and
     pages.yml              deploys site/ to GitHub Pages

FIRST-TIME PUBLISH  (one time, ~3 minutes):
   1. Log in to GitHub once:      gh auth login
   2. Create the repo and push:
        gh repo create cosl-watch --public --source . --remote origin --push
   3. Turn on Pages (Actions as the source):
        gh api -X POST repos/{owner}/cosl-watch/pages -f build_type=workflow
      (or in the browser: repo Settings > Pages > Source = "GitHub Actions")
   4. Actions tab > "Refresh COSL site" > Run workflow  (does the first build).
      Your site: https://<your-github-username>.github.io/cosl-watch/

After that it refreshes on its own every day. To force an update any time,
use the Actions tab "Run workflow" button, or just push a change.

Run the site locally to preview before publishing:
      python build_data.py
      python -m http.server 8000 --directory site   # then open localhost:8000
(Opening site/index.html directly as a file won't work — the browser blocks
data.json fetches over file://; it must be served over http.)


WHEN THE AUGUST AUCTIONS PASS
-----------------------------
The catalog for a sale disappears after the sale date. When COSL posts
next year's NWA dates, open cosl_watch.py and update the "saledate"
values in the WATCH list to the new M/D/YYYY dates. Nothing else changes.


READING THE DIGEST
------------------
Flags (colored pills), highest priority first:
   LIKELY IMPROVED  (red)   opening bid >= $8k — usually a structure, biggest spread
   RAW ACREAGE     (teal)   >= 10 acres — best $/acre plays
   CHEAP LOT       (blue)   <= $1,500 owed — wholesale lot volume play

Opening bid = taxes + penalties + interest owed. 2025 taxes are paid
separately to the county collector by Oct 15. All sales final; owners can
redeem up to 4 PM the business day before the sale, so parcels drop off
the list week to week — that's exactly why the weekly scrape is useful.
You receive a Limited Warranty Deed; budget for a quiet-title action
before you can resell with title insurance. Verify every parcel on
DataScoutPro (improvements, access, flood, liens) before bidding.

Research tool, not financial advice.
