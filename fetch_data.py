import json, urllib.request, ssl, datetime, sys, os

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

INDICES = ["H00922", "H20955"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ============ 交易日判定 ============
# 需求：只在 A 股交易日收盘后（北京时间 15:00 之后）抓取数据，避免非交易日白跑
# 和排队推迟导致的重复/无意义运行。非交易日直接退出（exit 0），不写数据、不告警。

# A 股休市日（法定节假日，仅周末之外补休/调休的特殊休市日）。
# 这里维护一份手动节假日表，含当年已确认及次年初部分调休休市日。
# 说明：该表无法覆盖未来全部节假日，但本脚本"工作日默认视为交易日"，
# 仅在命中表内休市日时才判定为非交易日；即便某节假日未收录导致白跑一次，
# 数据也仅是多抓取相同数据，不会污染（受下方 MIN_RECORDS 校验保护）。
A_SHARE_HOLIDAYS = {
    # 2026 年（农历/公历休市日，非周末部分）
    "2026-01-01", "2026-01-02",           # 元旦
    "2026-02-16", "2026-02-17", "2026-02-18", "2026-02-19",
    "2026-02-20", "2026-02-23",           # 春节（2/16-2/20 + 调休）
    "2026-04-06",                          # 清明
    "2026-05-01",                          # 劳动节
    "2026-06-19",                          # 端午
    "2026-09-25",                          # 中秋
    "2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06",
    "2026-10-07", "2026-10-08",           # 国庆
}


def is_trading_day(now):
    """判断当前时间是否为 A 股交易日收盘后。
    规则：
      1. 周末不交易；
      2. 命中休市日表不交易；
      3. 北京时间需已过 15:00（收盘后），避免抓取到当日不完整数据。
    """
    tz = ZoneInfo("Asia/Shanghai") if ZoneInfo else datetime.timezone(
        datetime.timedelta(hours=8))
    local = now.astimezone(tz)
    date_str = f"{local.year:04d}-{local.month:02d}-{local.day:02d}"
    # 周末
    if local.weekday() >= 5:
        return False
    # 法定休市日
    if date_str in A_SHARE_HOLIDAYS:
        return False
    # 收盘后
    if local.hour < 15:
        return False
    return True


# 手动触发（FORCE_UPDATE=1）时强制抓取，跳过交易日判定；
# 定时触发则只在交易日收盘后运行，避免非交易日白跑。
FORCE_UPDATE = os.environ.get("FORCE_UPDATE") == "1"
if not FORCE_UPDATE and not is_trading_day(datetime.datetime.now(datetime.timezone.utc)):
    print("非 A 股交易日或未到收盘时间（北京时间 15:00 后），跳过本次更新。")
    sys.exit(0)
# ============ 交易日判定结束 ============

def fetch(code):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=700)
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
# 定时模式（FORCE_UPDATE=0）保持严格下限 400 条；手动强制模式放宽到 50 条，
# 仅防止完全空数据污染，避免手动更新被 400 条下限卡住。
MIN_RECORDS = 50 if FORCE_UPDATE else 400
for c, series in data["indices"].items():
    if len(series) < MIN_RECORDS:
        print(f"校验失败：{c} 有效交易日仅 {len(series)} 条，低于下限 {MIN_RECORDS}，"
              f"疑似接口异常（空数据/结构变更），已中止写入以避免污染数据。", file=sys.stderr)
        sys.exit(1)

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)