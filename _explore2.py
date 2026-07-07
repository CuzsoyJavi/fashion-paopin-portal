import re, json, base64
from pathlib import Path

def load(f):
    h = Path(f).read_text(encoding="utf-8")
    m = re.search(r'atob\("([^"]+)"\)', h)
    return json.loads(base64.b64decode(m.group(1)).decode())

intern = load("index.html")
ext = load("外部商家版发布/index.html")
d = "2026-06-13"
bi = intern["byDate"][d]["internal"]
be = ext["byDate"][d]["internal"]

print("== overview internal CID[0] ==")
print(json.dumps(bi["overview"]["CID"][0], ensure_ascii=False))
print("== overview external CID[0] ==")
print(json.dumps(be["overview"]["CID"][0], ensure_ascii=False))
print("== overview external CID 全部行 ==")
for r in be["overview"]["CID"]:
    print("  ", json.dumps(r, ensure_ascii=False))

print("\n== 选品 products internal[0..2] ==")
for p in bi["products"][:3]:
    print("  ", json.dumps(p, ensure_ascii=False))
print("== 选品 products external[0..2] ==")
for p in be["products"][:3]:
    print("  ", json.dumps(p, ensure_ascii=False))
print("ext 选品 count:", len(be["products"]), " int 选品 count:", len(bi["products"]))

# client source html 是否在外部保留 & 是否含大盘
ce = next(c for c in ext["byDate"][d]["clients"] if c["name"]=="二两")
print("\n== external client 二两 source keys ==", list(ce["source"].keys()))
print("html length:", len(ce["source"]["html"]))
print("html head:", ce["source"]["html"][:200])

# sourceFiles 外部是否清空
print("\n== external bucket sourceFiles ==", json.dumps(ext["byDate"][d]["sourceFiles"], ensure_ascii=False)[:300])
print("== internal bucket sourceFiles count ==", len(intern["byDate"][d]["sourceFiles"]))
