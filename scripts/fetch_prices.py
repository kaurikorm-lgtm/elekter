"""Fetch Estonian day-ahead prices (Elering/Nord Pool) for the last 72 h and next 48 h into prices.json."""
import json, datetime as dt, urllib.request

now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
start, end = now - dt.timedelta(hours=72), now + dt.timedelta(hours=48)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
url = f"https://dashboard.elering.ee/api/nps/price?start={fmt(start)}&end={fmt(end)}"
out = {"fetched": int(now.timestamp()), "source": "Elering / Nord Pool", "ee": [], "fi": [], "lv": [], "lt": [], "error": None}
try:
    req = urllib.request.Request(url, headers={"User-Agent": "korm-ee-price-page"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)["data"]
    for zone in ("ee", "fi", "lv", "lt"):
        out[zone] = [[p["timestamp"], round(p["price"], 2)] for p in data.get(zone, [])]
except Exception as e:  # keep the page working even if the API is down
    out["error"] = str(e)
with open("prices.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print(len(out["ee"]), "EE points", out["error"] or "")
