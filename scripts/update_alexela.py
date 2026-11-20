"""Uuendab data.json alexela-osa Alexela "Vali ise" lehe hinnatabeli järgi.

Kasutus: python3 update_alexela.py <data.json>
Tabel: Periood | Fikseeritud baashind ("Detsember 2026 | 18,9 s/kwh", KM-ga, ilma marginaalita).
"""
import datetime as dt, html, json, re, sys, urllib.request
from zoneinfo import ZoneInfo

URL = "https://www.alexela.ee/et/eraklient/elekter/vali-ise"
ET = ["Jaanuar", "Veebruar", "Märts", "Aprill", "Mai", "Juuni", "Juuli", "August", "September", "Oktoober", "November", "Detsember"]
today = dt.datetime.now(ZoneInfo("Europe/Tallinn")).date()
path = sys.argv[1]
D = json.load(open(path, encoding="utf-8"))
A = D["alexela"]
before = json.dumps(A, ensure_ascii=False, sort_keys=True)

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (korm-ee-price-page)"})
h = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
cell = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
prices = {}
for tr in re.findall(r"<tr.*?</tr>", h, re.S):
    c = [cell(x) for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
    if len(c) >= 2:
        m = re.match(r"^(\w+) (\d{4})$", c[0])
        p = re.match(r"^(\d+(?:[.,]\d+)?)\s*s/kwh", c[1], re.I)
        if m and p and m.group(1).capitalize() in ET:
            prices[(int(m.group(2)), ET.index(m.group(1).capitalize()) + 1)] = float(p.group(1).replace(",", "."))
if len(prices) < 3:
    sys.exit(f"Alexela: hinnatabelit ei leitud ({len(prices)} rida)")

label = lambda y, m: f"{ET[m - 1]} {y}"
GEN = ["jaanuari", "veebruari", "märtsi", "aprilli", "mai", "juuni", "juuli", "augusti", "septembri", "oktoobri", "novembri", "detsembri"]
nxt = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
after = (nxt[0] + 1, 1) if nxt[1] == 12 else (nxt[0], nxt[1] + 1)
deadline = f"28.{today.month:02d}.{today.year}"
A["nextMonth"] = label(*nxt)
if nxt in prices:
    A["nextPrice"] = prices[nxt]
    A["publishNote"] = (f"Alexela avaldas {GEN[nxt[1] - 1]} baashinna ({str(prices[nxt]).replace('.', ',')} s/kWh). "
                        f"Valik tuleb teha äpis hiljemalt {deadline}; {GEN[after[1] - 1]} hind avaldatakse hiljemalt 20.{nxt[1]:02d}.{nxt[0]}.")
else:
    A["nextPrice"] = None
    A["publishNote"] = (f"{GEN[nxt[1] - 1].capitalize()} baashind avaldatakse hiljemalt 20.{today.month:02d}.{today.year}; "
                        f"valik tuleb teha äpis hiljemalt {deadline}.")
# known: kõik avaldatud hinnad alates varaseimast juba teadaolevast kuust
known = {k["month"]: k for k in A.get("known", [])}
start = min([(int(k.split()[1]), ET.index(k.split()[0]) + 1) for k in known] or [nxt])
for k in sorted(prices):
    if k >= start and label(*k) not in known:
        known[label(*k)] = {"month": label(*k), "price": prices[k]}
A["known"] = sorted(known.values(), key=lambda k: (int(k["month"].split()[1]), ET.index(k["month"].split()[0])))

if json.dumps(A, ensure_ascii=False, sort_keys=True) != before:
    D["updated"] = today.isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Alexela uuendatud: {A['nextMonth']} {A['nextPrice']}")
else:
    print(f"Alexela muutmata: {A['nextMonth']} {A['nextPrice']}")
