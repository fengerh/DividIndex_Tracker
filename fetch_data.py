import json, urllib.request, ssl, datetime, sys

INDICES = ["H00922", "H20955"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def fetch(code):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=500)
    url = (f"https://www.csindex.com.cn/csindex-home/perf/index-perf"
           f"?indexCode={code}&startDate={start:%Y%m%d}&endDate={end:%Y%m%d}")
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        "Referer": "https://www.csindex.com.cn/"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        j = json.loads(r.read())
    lst = j.get("data") or j.get("result") or j
    out = []
    for it in lst:
        date = str(it.get("tradeDate") or it.get("date") or "")[:10]
        try:
            close = float(it.get("close"))
        except (TypeError, ValueError):
            continue
        if date and close:
            out.append({"date": date, "close": close})
    out.sort(key=lambda x: x["date"])
    return out

data = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "indices": {}}
for c in INDICES:
    data["indices"][c] = fetch(c)
    print(c, len(data["indices"][c]), "个交易日")

# 结果校验：任一只指数有效条数过低，视为接口异常，中止以免覆盖上一版 data.json
MIN_RECORDS = 400
for c, series in data["indices"].items():
    if len(series) < MIN_RECORDS:
        print(f"校验失败：{c} 有效交易日仅 {len(series)} 条，低于下限 {MIN_RECORDS}，"
              f"疑似接口异常（空数据/结构变更），已中止写入以避免污染数据。", file=sys.stderr)
        sys.exit(1)

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)
