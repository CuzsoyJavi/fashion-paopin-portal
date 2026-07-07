import re, json, base64, difflib
from pathlib import Path
import importlib.util

ROOT = Path(".").resolve()
spec = importlib.util.spec_from_file_location("bip", ROOT / "build_internal_portal.py")
bip = importlib.util.module_from_spec(spec); spec.loader.exec_module(bip)

# 部署版 0613 二两 source.html
h = Path("index.html").read_text(encoding="utf-8")
dep = json.loads(base64.b64decode(re.search(r'atob\("([^"]+)"\)', h).group(1)).decode())
old_html = next(c for c in dep["byDate"]["2026-06-13"]["clients"] if c["name"]=="二两")["source"]["html"]

# 新渲染 0613 二两 source.html
new_md = (ROOT/"每日md数据源"/"二两_日报_20260613.md").read_text(encoding="utf-8")
new_html = bip.markdown_to_html(new_md)

# 只看包含「趋势」的差异块
old_lines = old_html.split("\n"); new_lines = new_html.split("\n")
diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=1))
print("差异行数:", len(diff))
# 找趋势相关
for i,l in enumerate(diff):
    if "趋势" in l or "nan" in l or "05-31" in l or "06-13" in l:
        print(l[:120])
print("---- 是否仅趋势区不同 ----")
non_trend = [l for l in diff if l.startswith(("+","-")) and not l.startswith(("+++","---")) and ("nan" not in l) and ("0.00" not in l) and not re.search(r"0[56]-\d{2}", l) and "趋势" not in l]
print("非趋势相关的增删行数:", len(non_trend))
for l in non_trend[:20]: print("  非趋势diff:", l[:120])
