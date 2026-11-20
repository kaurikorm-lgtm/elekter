import re, html, urllib.request
req = urllib.request.Request("https://www.alexela.ee/et/eraklient/elekter/vali-ise", headers={"User-Agent": "Mozilla/5.0 (korm-ee-price-page)"})
h = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S))))
print(len(h), len(t))
for m in re.finditer(r"s/kWh|senti|baashind|fikseeritud", t, re.I):
    print("...", t[max(0, m.start()-200):m.end()+120])
for tr in re.findall(r"<tr.*?</tr>", h, re.S)[:40]:
    print(" |", " | ".join(re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",c))).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)))
