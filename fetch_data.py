import json, urllib.request, ssl, datetime, os

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

new_indices = {}
for c in INDICES:
    new_indices[c] = fetch(c)
    print(c, len(new_indices[c]), "个交易日")

# 读取现有 data.json，若指数数据未变化则保持 updated 不变，避免重复提交
old_data = None
try:
    with open("data.json", encoding="utf-8") as f:
        old_data = json.load(f)
except (OSError, ValueError):
    old_data = None

if old_data and old_data.get("indices") == new_indices:
    print("指数数据无变化，跳过更新 data.json")
else:
    data = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "indices": new_indices}
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print("数据已更新")