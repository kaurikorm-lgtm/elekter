"""Fetch Estonian day-ahead prices (Elering/Nord Pool) for the last 72 h and next 48 h into prices.json.

Elering's API sometimes publishes the next day's prices hours later than Nord Pool, so if
tomorrow is missing we fill it from the Nord Pool data portal API.
"""
import json, datetime as dt, urllib.request

ZONES = ("ee", "fi", "lv", "lt")
now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
start, end = now - dt.timedelta(hours=72), now + dt.timedelta(hours=48)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
out = {"fetched": int(now.timestamp()), "source": "Elering / Nord Pool", "ee": [], "fi": [], "lv": [], "lt": [], "error": None}


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "korm-ee-price-page", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


try:
    data = get_json(f"https://dashboard.elering.ee/api/nps/price?start={fmt(start)}&end={fmt(end)}")["data"]
    for zone in ZONES:
        out[zone] = [[p["timestamp"], round(p["price"], 2)] for p in data.get(zone, [])]
except Exception as e:  # keep the page working even if the API is down
    out["error"] = str(e)

# Täienda Nord Pooli andmeportaalist, kui Eleringil homseid hindu veel pole.
cet = dt.timezone(dt.timedelta(hours=1))  # tarnepäev on CET järgi (suveaja nihe pole siin oluline)
for day_offset in (0, 1):
    day = (now.astimezone(cet) + dt.timedelta(days=day_offset)).date()
    last = out["ee"][-1][0] if out["ee"] else 0
    try:
        np = get_json("https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
                      f"?date={day.isoformat()}&market=DayAhead&deliveryArea=EE,FI,LV,LT&currency=EUR")
        entries = (np or {}).get("multiAreaEntries") or []
        added = 0
        for e in entries:
            t = int(dt.datetime.fromisoformat(e["deliveryStart"].replace("Z", "+00:00")).timestamp())
            if t <= last or t > end.timestamp():
                continue
            area = e.get("entryPerArea") or {}
            for zone in ZONES:
                v = area.get(zone.upper())
                if v is not None:
                    out[zone].append([t, round(float(v), 2)])
            added += 1
        if added:
            print(f"Nord Pool: lisatud {added} punkti päevale {day}")
    except Exception as e:
        print(f"Nord Pool {day}: {e}")

for zone in ZONES:
    out[zone].sort(key=lambda p: p[0])
with open("prices.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print(len(out["ee"]), "EE points", out["error"] or "")
