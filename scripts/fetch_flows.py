"""Fetch Estonia's cross-border flows (Elering) into flows.json.

- trade:  planned commercial flow per 15 min (day-ahead + intraday), last 24 h and as far ahead as published.
          Sign is from Estonia's side: negative = import into Estonia, positive = export.
- cap:    net transfer capacity (NTC) per 15 min for the Finland (Estlink) and Latvia borders.
- latest: last measured flow on each border; system: last measured production and consumption.
"""
import json, datetime as dt, urllib.request

B = "https://dashboard.elering.ee/api"
now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
f = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.000Z")
q = f"start={f(now - dt.timedelta(hours=24))}&end={f(now + dt.timedelta(hours=40))}"


def get(path):
    req = urllib.request.Request(f"{B}{path}", headers={"User-Agent": "korm-ee-price-page"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]


r2 = lambda v: None if v is None else round(v, 1)
out = {"fetched": int(now.timestamp()), "source": "Elering", "trade": [], "cap": {}, "latest": None, "system": None, "error": None}
try:
    out["trade"] = [[p["timestamp"], r2(p["ee_fi"]), r2(p["ee_lv"])] for p in get(f"/transmission/cross-border-planned-trade?{q}")]
    cap = get(f"/transmission/cross-border-capacity?{q}")
    for g in ("FI", "LV"):
        out["cap"][g] = [[p["timestamp"], r2(p["in_ntc"]), r2(p["out_ntc"])] for p in cap.get(g, [])]
    m = get("/transmission/cross-border/latest")[0]
    out["latest"] = {k: (m[k] if k == "timestamp" else r2(m[k])) for k in ("timestamp", "finland", "latvia", "estlink_1", "estlink_2")}
    s = get("/system/latest")[0]
    out["system"] = {"timestamp": s["timestamp"], "production": r2(s["production"]), "consumption": r2(s["consumption"]),
                     "renewable": r2(s.get("production_renewable"))}
except Exception as e:  # keep the page working even if the API is down
    out["error"] = str(e)
with open("flows.json", "w") as fh:
    json.dump(out, fh, separators=(",", ":"))
print(len(out["trade"]), "trade points", out["error"] or "")
