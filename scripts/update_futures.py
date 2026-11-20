"""Uuendab data.json futuurid (months, quarters, futuresDate), history ja eeSpread automaatselt.

Kasutus: python3 update_futures.py <data.json> [<daily.csv>]
- Futuurid: sahkotutka.fi/futuurit (Euronext Nord Pool sulgemishinnad, €/MWh KM-ta),
  varuallikas parassahko.fi/sahkon-hintaennuste (snt/kWh KM-ta -> ×10).
- eeSpread: haru "data" daily.csv põhjal (talv nov–märts, suvi apr–okt, viimased 30 päeva).
Muudab faili ainult siis, kui midagi päriselt muutus. Väljundis on kokkuvõte logi jaoks.
"""
import csv, datetime as dt, html, json, math, os, re, sys, urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Tallinn")
today = dt.datetime.now(TZ).date()
data_path = sys.argv[1]
csv_path = sys.argv[2] if len(sys.argv) > 2 else None
D = json.load(open(data_path, encoding="utf-8"))
before = json.dumps(D, ensure_ascii=False, sort_keys=True)
log = []

FI_MONTHS = ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"]
ET_LABELS = ["Jaan", "Veebr", "Märts", "Apr", "Mai", "Juuni", "Juuli", "Aug", "Sept", "Okt", "Nov", "Dets"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (korm-ee-price-page)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def text(s):
    s = re.sub(r"<[^>]+>", " ", s).replace("­", "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def num(s):
    s = s.replace("−", "-").replace("−", "-").replace(",", ".").replace(" ", "")
    m = re.match(r"^-?\d+(\.\d+)?", s)
    return float(m.group(0)) if m else None


def rows(h):
    for t in re.findall(r"<table.*?</table>", h, re.S):
        for tr in re.findall(r"<tr.*?</tr>", t, re.S):
            yield [text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]


def month_of(label):
    """'Joulukuu 2026', 'joulukuu 2026 *' -> (2026, 12); None muidu."""
    m = re.match(r"^([a-zäö]+)kuu (\d{4})", label.lower())
    if m and m.group(1) in FI_MONTHS:
        return int(m.group(2)), FI_MONTHS.index(m.group(1)) + 1
    return None


def quarter_of(label):
    l = label.lower()
    m = re.match(r"^q([1-4]) (\d{4})", l)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = re.match(r"^(tammi|huhti|heinä|loka)[–-]\w+ (\d{4})", l)
    if m:
        return int(m.group(2)), ["tammi", "huhti", "heinä", "loka"].index(m.group(1)) + 1
    return None


def prev_weekday(d):
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def parse_sahkotutka():
    h = get("https://sahkotutka.fi/futuurit")
    t = text(h)
    m = re.search(r"päivältä (\d{1,2})\. ?([a-zäö]+)kuuta (\d{4})", t)
    if not m or m.group(2) not in FI_MONTHS:
        raise ValueError("kuupäeva ei leitud")
    date = dt.date(int(m.group(3)), FI_MONTHS.index(m.group(2)) + 1, int(m.group(1)))
    months, quarters = {}, {}
    for r in rows(h):
        if len(r) < 5:
            continue
        sysp, fi = num(r[2]), num(r[4])
        if sysp is None or fi is None:
            continue
        est = "*" in r[0]
        if (k := month_of(r[0])):
            months[k] = (sysp, fi, est)
        elif (k := quarter_of(r[0])):
            quarters[k] = (sysp, fi, est)
    return date, months, quarters


def parse_parassahko():
    h = get("https://parassahko.fi/sahkon-hintaennuste")
    t = text(h)
    m = re.search(r"päivitetty (\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    if not m:
        raise ValueError("kuupäeva ei leitud")
    upd = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    date = prev_weekday(upd)  # leht näitab eelmise kauplemispäeva sulgemishindu
    months, quarters = {}, {}
    for r in rows(h):
        if len(r) < 4:
            continue
        sysp, fi = num(r[1]), num(r[3])
        if sysp is None or fi is None:
            continue
        est = "¹" in r[2] or "²" in r[2]
        if (k := month_of(r[0])):
            months[k] = (round(sysp * 10, 2), round(fi * 10, 2), est)
        elif (k := quarter_of(r[0])):
            quarters[k] = (round(sysp * 10, 2), round(fi * 10, 2), est)
    return date, months, quarters


def parse_ddmmyyyy(s):
    try:
        d, m, y = (int(x) for x in s.split("."))
        return dt.date(y, m, d)
    except Exception:
        return None


# ---------- Futuurid ----------
cur = parse_ddmmyyyy(D.get("futuresDate", "")) or dt.date(2000, 1, 1)
if os.environ.get("FUTURES_FORCE"):
    cur = dt.date(2000, 1, 1)
latest_possible = today if today.weekday() < 5 else prev_weekday(today)
result = None
if cur >= latest_possible:
    log.append(f"futuurid juba värsked ({D['futuresDate']})")
else:
    for name, fn in (("sahkotutka.fi", parse_sahkotutka), ("parassahko.fi", parse_parassahko)):
        try:
            date, months, quarters = fn()
        except Exception as e:
            log.append(f"{name}: viga {e}")
            continue
        nxt = (today.year + today.month // 12, today.month % 12 + 1)
        need = [nxt, ((nxt[0] + nxt[1] // 12), nxt[1] % 12 + 1)]
        ok = all(k in months for k in need) and all(0 < v[0] < 2000 and -500 < v[1] < 2000 for v in months.values())
        if not ok:
            log.append(f"{name}: tabel ei sobinud ({len(months)} kuud)")
            continue
        if date <= cur:
            log.append(f"{name}: andmed {date} pole uuemad kui {D['futuresDate']}")
            continue
        result = (name, date, months, quarters)
        break

if result:
    name, date, months, quarters = result
    out = []
    y, m = today.year, today.month
    for _ in range(6):
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        if (y, m) not in months:
            break
        s, f, _e = months[(y, m)]
        out.append({"period": f"{y}-{m:02d}", "label": f"{ET_LABELS[m - 1]} {y}", "system": s, "fi": f})
    curq = (today.year, (today.month - 1) // 3 + 1)
    qs = []
    for k in sorted(quarters):
        if k > curq and not quarters[k][2] and len(qs) < 4:
            s, f, _e = quarters[k]
            qs.append({"label": f"Q{k[1]} {k[0]}", "winter": k[1] in (1, 4), "system": s, "fi": f})
    D["months"] = out
    if qs:
        D["quarters"] = qs
    D["futuresDate"] = date.strftime("%d.%m.%Y")
    log.append(f"futuurid {D['futuresDate']} ({name}): " + ", ".join(f"{x['label']} {x['fi']}" for x in out[:3]))

    # history: üks kirje nädalas (esimene sel nädalal saadud sulgemishind)
    H = D.setdefault("history", [])
    wk = date.isocalendar()[:2]
    if not any(dt.date.fromisoformat(h["date"]).isocalendar()[:2] == wk for h in H):
        H.append({"date": date.isoformat(), "approx": False, "fi": {x["period"]: x["fi"] for x in out[:3]}})
        H.sort(key=lambda h: h["date"])
        del H[:-12]
        log.append(f"history: lisatud {date}")

# ---------- Eesti–Soome hinnavahe ----------
if csv_path:
    try:
        rs = list(csv.DictReader(open(csv_path)))
        last = dt.date.fromisoformat(rs[-1]["date"])
        yr = [r for r in rs if dt.date.fromisoformat(r["date"]) > last - dt.timedelta(days=365)]
        bym = {}
        for r in yr:
            bym.setdefault(r["date"][:7], []).append(float(r["spread"]))
        mavg = {k: sum(v) / len(v) for k, v in bym.items()}
        w = [v for k, v in mavg.items() if int(k[5:]) in (11, 12, 1, 2, 3)]
        s = [v for k, v in mavg.items() if 4 <= int(k[5:]) <= 10]
        last30 = [float(r["spread"]) for r in rs if dt.date.fromisoformat(r["date"]) > last - dt.timedelta(days=30)]
        c = sum(last30) / len(last30)

        def rng(typ):
            lo, hi = math.floor(min(typ, c) / 10) * 10, math.ceil(max(typ, c) / 10) * 10
            return [lo, max(hi, lo + 30)]

        es = D["eeSpread"]
        changed = []
        if w:
            wt = sum(w) / len(w)
            nw = rng(wt)
            if nw != es["winter"]:
                es["winter"] = nw
                changed.append(f"talv {nw}")
        if s:
            st = sum(s) / len(s)
            if 4 <= today.month <= 10:
                ns = rng(st)
            else:
                mid = round(st / 10) * 10
                ns = [max(0, mid - 10), mid + 10]
            if ns != es["summer"]:
                es["summer"] = ns
                changed.append(f"suvi {ns}")
        if changed:
            season = "talvekuude" if not (4 <= today.month <= 10) else "suvekuude"
            typ = (sum(w) / len(w)) if season == "talvekuude" else (sum(s) / len(s))
            es["note"] = (f"Vahemik põhineb viimase 12 kuu {season} keskmisel Eesti–Soome hinnavahel "
                          f"(umbes {round(typ)} €/MWh) ja viimase 30 päeva keskmisel (umbes {round(c)} €/MWh).")
            log.append("eeSpread: " + ", ".join(changed))
        else:
            log.append(f"eeSpread muutmata (30 p keskmine {c:.1f})")
    except Exception as e:
        log.append(f"eeSpread: viga {e}")

after = json.dumps(D, ensure_ascii=False, sort_keys=True)
if after != before:
    D["updated"] = today.isoformat()
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=2)
        f.write("\n")
    log.append("data.json muudetud")
print("\n".join(log))
