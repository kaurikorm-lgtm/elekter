"""Debug: dump futures table rows from sahkotutka.fi and parassahko.fi."""
import re, html, urllib.request
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (korm-ee-price-page)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")
def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
for url in ("https://sahkotutka.fi/futuurit", "https://parassahko.fi/sahkon-hintaennuste"):
    try:
        h = get(url)
    except Exception as e:
        print("FAIL", url, e); continue
    print("==", url, len(h))
    for m in re.finditer(r"(päivältä|päivitetty|Päivitetty|päätös)[^<]{0,80}", h):
        print("DATE?", text(m.group(0)))
    for i, t in enumerate(re.findall(r"<table.*?</table>", h, re.S)):
        print("-- table", i)
        for tr in re.findall(r"<tr.*?</tr>", t, re.S)[:30]:
            print("  |", " | ".join(text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)))
    if "<table" not in h:
        print(text(h)[:3000])
