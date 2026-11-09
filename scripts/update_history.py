"""Keep a daily archive of Baltic/Finnish day-ahead prices and derive the Estonia–Finland spread.

Usage: python3 update_history.py <archive_dir> <site_dir>
- <archive_dir>/daily.csv : date,ee,fi,lv,spread,decoupled  (€/MWh, VAT 0; decoupled = share of 15-min periods where EE-FI > 1 €/MWh)
- <site_dir>/spread.json  : monthly summary + last 30 days, used by the web page and the daily update task
"""
import csv, json, sys, os, datetime as dt, urllib.request
from collections import defaultdict
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Tallinn")
arch, site = sys.argv[1], sys.argv[2]
path = os.path.join(arch, "daily.csv")
rows = {}
if os.path.exists(path):
    with open(path) as f:
        for r in csv.DictReader(f):
            rows[r["date"]] = r

today = dt.datetime.now(TZ).date()
yesterday = today - dt.timedelta(days=1)
start_day = (max(dt.date.fromisoformat(d) for d in rows) + dt.timedelta(days=1)) if rows else today - dt.timedelta(days=400)


def fetch(d0, d1):
    s = dt.datetime.combine(d0, dt.time(), TZ).astimezone(dt.timezone.utc)
    e = dt.datetime.combine(d1 + dt.timedelta(days=1), dt.time(), TZ).astimezone(dt.timezone.utc)
    f = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    url = f"https://dashboard.elering.ee/api/nps/price?start={f(s)}&end={f(e - dt.timedelta(seconds=1))}"
    req = urllib.request.Request(url, headers={"User-Agent": "korm-ee-price-page"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["data"]


d = start_day
while d <= yesterday:
    d1 = min(d + dt.timedelta(days=180), yesterday)
    data = fetch(d, d1)
    per = defaultdict(lambda: defaultdict(dict))  # day -> ts -> zone -> price
    for z in ("ee", "fi", "lv"):
        for p in data.get(z, []):
            day = dt.datetime.fromtimestamp(p["timestamp"], TZ).date().isoformat()
            per[day][p["timestamp"]][z] = p["price"]
    for day, ts in per.items():
        if not (d.isoformat() <= day <= d1.isoformat()):
            continue
        pts = [v for v in ts.values() if "ee" in v and "fi" in v]
        if not pts:
            continue
        avg = lambda z: sum(v[z] for v in ts.values() if z in v) / max(1, sum(1 for v in ts.values() if z in v))
        rows[day] = {"date": day, "ee": f"{avg('ee'):.2f}", "fi": f"{avg('fi'):.2f}", "lv": f"{avg('lv'):.2f}",
                     "spread": f"{sum(v['ee'] - v['fi'] for v in pts) / len(pts):.2f}",
                     "decoupled": f"{sum(1 for v in pts if v['ee'] - v['fi'] > 1) / len(pts):.3f}"}
    d = d1 + dt.timedelta(days=1)

os.makedirs(arch, exist_ok=True)
with open(path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["date", "ee", "fi", "lv", "spread", "decoupled"])
    w.writeheader()
    for k in sorted(rows):
        w.writerow(rows[k])


def summ(rs):
    n = len(rs)
    if not n:
        return None
    m = lambda k: round(sum(float(r[k]) for r in rs) / n, 2)
    return {"days": n, "ee": m("ee"), "fi": m("fi"), "lv": m("lv"), "spread": m("spread"), "decoupled": round(m("decoupled"), 3)}


months = defaultdict(list)
for r in rows.values():
    months[r["date"][:7]].append(r)
recent = [rows[k] for k in sorted(rows)[-30:]]
out = {"updated": today.isoformat(), "source": "Elering / Nord Pool päev-ette hinnad",
       "last30": summ(recent),
       "months": [{"month": k, **summ(v)} for k, v in sorted(months.items())][-13:]}
with open(os.path.join(site, "spread.json"), "w") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"{len(rows)} days in archive, last30 spread {out['last30'] and out['last30']['spread']}")
