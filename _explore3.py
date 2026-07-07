import re, json, base64, math
from pathlib import Path

def load(f):
    h = Path(f).read_text(encoding="utf-8")
    m = re.search(r'atob\("([^"]+)"\)', h)
    return json.loads(base64.b64decode(m.group(1)).decode())

intern = load("index.html"); ext = load("外部商家版发布/index.html")
spend_map = {}; roi_map = {}
for d in intern["dates"]:
    bi = intern["byDate"][d]["internal"]["products"]
    be = ext["byDate"][d]["internal"]["products"]
    key = lambda p: (p["link"], p["rank"], p["name"])
    em = {key(p): p for p in be}
    for p in bi:
        e = em.get(key(p))
        if not e: continue
        if p.get("spend") is not None:
            spend_map.setdefault(e["spend"], []).append(p["spend"])
        if p.get("roi") is not None:
            roi_map.setdefault(e["roi"], []).append(p["roi"])

print("== 消耗区间 -> 实际值范围 ==")
for k in sorted(spend_map, key=lambda s: min(spend_map[s])):
    vs = spend_map[k]
    print(f"  '{k}': min={min(vs):.2f} max={max(vs):.2f} n={len(vs)}")
print("\n== ROI区间 -> 实际值范围 ==")
for k in sorted(roi_map, key=lambda s: min(roi_map[s])):
    vs = roi_map[k]
    print(f"  '{k}': min={min(vs):.3f} max={max(vs):.3f} n={len(vs)}")

# 验证我的猜想公式
def roi_band(v):
    lo = math.floor(v*10)/10
    return f"{lo:.1f}到{lo+0.1:.1f}"
bad = [(v,k,roi_band(v)) for k,vs in roi_map.items() for v in vs if roi_band(v)!=k]
print("\nROI公式不符:", len(bad), bad[:8])
