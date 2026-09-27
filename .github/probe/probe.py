# TEMPORARY: dumps cosl.org page structure into the Actions log. Remove after.
import re, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
B = "https://www.cosl.org"

def body(path, params=None, maxlen=9000):
    print("\n" + "=" * 100 + f"\n### {path} {params or ''}")
    r = requests.get(B + path, params=params, headers=H, timeout=60)
    print("status", r.status_code, "bytes", len(r.text))
    s = BeautifulSoup(r.text, "html.parser")
    for sc in s.find_all("script"):
        src = sc.get("src")
        txt = (sc.string or "").strip()
        if src and "jquery" not in src.lower() and "bootstrap" not in src.lower():
            print("SCRIPT src:", src)
        if txt and re.search(r"ajax|fetch|url|\.json|/Home/|/api/", txt, re.I):
            print("SCRIPT inline:", txt[:2500])
    for tag in s(["script", "style", "nav", "header", "footer", "head"]):
        tag.decompose()
    main = s.find("main") or s.find(class_=re.compile("body-content|container|content", re.I)) or s.body
    html = re.sub(r"\s+", " ", str(main))
    print("MAINHTML:", html[:maxlen])
    return r.text

body("/Home/PostAuctionView", {"county": "BENTON"}, 12000)
body("/Home/PostAuctionView", {"county": "WASHINGTON"}, 4000)
body("/Home/PostSaleResult", {"county": "BENT"}, 8000)
body("/Home/CatalogView", {"county": "BENT", "saledate": "8/11/2026 10:00:00 AM"}, 4000)
