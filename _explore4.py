import re, json, base64
from pathlib import Path

def load(f):
    h = Path(f).read_text(encoding="utf-8")
    m = re.search(r'atob\("([^"]+)"\)', h)
    return json.loads(base64.b64decode(m.group(1)).decode())

intern = load("index.html")
for d in intern["dates"]:
    bi = intern["byDate"][d]["internal"]
    print(d, "overallDelta=", json.dumps(bi.get("overallDelta"), ensure_ascii=False))
    print("   overallText CID:", (bi.get("overallText",{}).get("CID","") or "")[:90])
    print("   overallText 小店:", (bi.get("overallText",{}).get("小店","") or "")[:90])
