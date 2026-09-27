# TEMPORARY: dumps cosl.org page structure into the Actions log so the
# post-auction parser can be written against the real markup. Remove after.
import re, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
B = "https://www.cosl.org"

def dump(path, params=None, rows=3):
    print("\n" + "=" * 100 + f"\n### {path} {params or ''}")
    try:
        r = requests.get(B + path, params=params, headers=H, timeout=60)
    except Exception as e:
        print("EXC", e); return None
    print("status", r.status_code, "final", r.url, "bytes", len(r.text))
    s = BeautifulSoup(r.text, "html.parser")
    print("title:", s.title.get_text(strip=True) if s.title else None)
    for f in s.find_all("form"):
        print("FORM", f.get("action"), f.get("method"),
              [(i.get("name"), i.get("type"), i.get("value")) for i in f.find_all(["input", "select"])][:20])
        for sel in f.find_all("select"):
            print("  SELECT", sel.get("name"), [(o.get("value"), o.get_text(strip=True)) for o in sel.find_all("option")][:90])
    tables = s.find_all("table")
    print("tables:", [len(t.find_all("tr")) for t in tables])
    for ti, t in enumerate(tables):
        trs = t.find_all("tr")
        if len(trs) < 2: continue
        print(f"-- table {ti} attrs={t.attrs} rows={len(trs)}")
        print("HEADER:", [c.get_text(" ", strip=True) for c in trs[0].find_all(["th", "td"])])
        for tr in trs[1:1 + rows]:
            print("ROW:", [c.get_text(" ", strip=True)[:120] for c in tr.find_all(["th", "td"])])
            print("ROWHTML:", str(tr)[:1500])
    links = sorted({a["href"] for a in s.find_all("a", href=True)})
    print("LINKS(filtered):", [l for l in links if re.search(r"county|sale|catalog|post|parcel|page", l, re.I)][:150])
    print("TEXT-SNIPPETS:", [t.strip()[:200] for t in s.find_all(string=re.compile(r"price|minimum|offer|bid|purchase", re.I))][:15])
    return s

dump("/Home/Contents")
dump("/Home/PostAuction")
for c in ["BENTON", "WASHINGTON", "CARROLL", "MADISON"]:
    dump("/Home/PostAuctionView", {"county": c}, rows=3 if c == "BENTON" else 1)
dump("/Home/PostAuctionView", {"county": "BENT"}, rows=1)
