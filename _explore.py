import re, json, base64
from pathlib import Path

def load(f):
    h = Path(f).read_text(encoding="utf-8")
    m = re.search(r'atob\("([^"]+)"\)', h)
    return json.loads(base64.b64decode(m.group(1)).decode())

intern = load("index.html")
ext = load("外部商家版发布/index.html")

print("== 顶层 keys ==")
print("internal:", list(intern.keys()))
print("external:", list(ext.keys()))
print("internal dates:", intern["dates"])
print("external dates:", ext["dates"])

d = "2026-06-13"
bi = intern["byDate"][d]
be = ext["byDate"][d]
print("\n== byDate[%s] keys ==" % d)
print("internal bucket keys:", list(bi.keys()))
print("external bucket keys:", list(be.keys()))

print("\n== internal.internal(大盘) keys ==", list(bi.get("internal", {}).keys()) if "internal" in bi else "无")
print("== external.internal(大盘) keys ==", list(be.get("internal", {}).keys()) if "internal" in be else "无")

print("\n== 客户对象字段对比 (二两) ==")
ci = next((c for c in bi["clients"] if c["name"]=="二两"), {})
ce = next((c for c in be["clients"] if c["name"]=="二两"), {})
print("internal client keys:", list(ci.keys()))
print("external client keys:", list(ce.keys()))

print("\n-- internal 二两 products[0] --")
print(json.dumps(ci.get("products",[{}])[0], ensure_ascii=False)[:500])
print("-- external 二两 products[0] --")
print(json.dumps(ce.get("products",[{}])[0], ensure_ascii=False)[:500])

print("\n-- internal 二两 effects --")
print(json.dumps(ci.get("effects",{}), ensure_ascii=False)[:600])
print("-- external 二两 effects --")
print(json.dumps(ce.get("effects",{}), ensure_ascii=False)[:600])

# 选品 products in internal bucket (大盘)
print("\n== internal bucket.internal.products[0] (选品) ==")
ip = bi.get("internal",{}).get("products",[])
print("count:", len(ip))
if ip: print(json.dumps(ip[0], ensure_ascii=False)[:600])
print("== external 选品 在哪里 ==")
# external selection
ep = be.get("internal",{}).get("products",[]) if "internal" in be else be.get("products",[])
print("ext keys for selection? bucket keys again:", list(be.keys()))
