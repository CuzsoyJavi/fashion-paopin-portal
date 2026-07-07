import re, json, base64
from pathlib import Path

ROOT = Path(".")
INT = ["index.html", "内部版跑品客户门户.html", "内部直客销售版跑品客户门户.html"]
EXT = ["外部商家客户版跑品客户门户.html", "外部商家版发布/index.html"]

def load(f):
    h = Path(f).read_text(encoding="utf-8")
    m = re.search(r'atob\("([^"]+)"\)', h)
    return json.loads(base64.b64decode(m.group(1)).decode())

ok = True
print("===== 内部版 =====")
for f in INT:
    d = load(f)
    b = d["byDate"]["2026-06-14"]
    er = next(c for c in b["clients"] if c["name"]=="二两")["trend"]
    big = b["internal"]
    print(f"{f}: dates={d['dates']} 客户={len(b['clients'])} 二两trend={len(er)}天 末={er[-1]} 大盘keys={sorted(big.keys())} 选品={len(big['products'])} overview样例={big['overview']['CID'][0].get('消耗(万元)') is not None}")
    if d['dates'] != ['2026-06-12','2026-06-13','2026-06-14']: ok=False; print("  ✗ 日期错")
    if er[-1]['日期'] != '06-14': ok=False; print("  ✗ 趋势末点错")

print("\n===== 外部版（脱敏）=====")
for f in EXT:
    d = load(f)
    b = d["byDate"]["2026-06-14"]
    big = b["internal"]
    p0 = big["products"][0]
    ov0 = big["overview"]["CID"][0]
    er = next(c for c in b["clients"] if c["name"]=="二两")["trend"]
    print(f"{f}:")
    print(f"  dates={d['dates']} 客户={len(b['clients'])} 二两trend={len(er)}天 末={er[-1]}")
    print(f"  大盘keys={sorted(big.keys())} (应只有date/sourceName/overview/products)")
    print(f"  sourceFiles={b['sourceFiles']} (应为[])")
    print(f"  选品样例 spend={p0.get('spend')!r} roi={p0.get('roi')!r} 含price?={'price' in p0}")
    print(f"  overview样例={ov0} (占比应为整数,无消耗/ROI)")
    # 校验脱敏
    if 'overallText' in big or 'fluctuation' in big or 'source' in big: ok=False; print("  ✗ 大盘未脱敏")
    if b['sourceFiles'] != []: ok=False; print("  ✗ sourceFiles未清空")
    if 'price' in p0 or 'bid' in p0 or 'creativeCount' in p0: ok=False; print("  ✗ 选品字段未脱敏")
    if not isinstance(p0.get('spend'), str) or '到' not in str(p0.get('spend')) and '+' not in str(p0.get('spend')): ok=False; print("  ✗ 消耗未区间化")
    if '消耗(万元)' in ov0 or '下单ROI' in ov0: ok=False; print("  ✗ overview未脱敏")
    try:
        int(ov0['消耗占比(%)'])
    except: ok=False; print("  ✗ 占比非整数")

print("\n", "ALL_OK ✓" if ok else "HAS_ISSUE ✗")
