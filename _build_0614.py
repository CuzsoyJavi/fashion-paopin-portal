#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑品客户 Portal 全量重建：内部全量 + 外部脱敏，保留最近三天。
用法：
  python3 _build_0614.py             # 自动选择最新日报源，dry-run 不写 HTML
  python3 _build_0614.py 0617        # 指定 MMDD，dry-run 不写 HTML
  python3 _build_0614.py 0617 write  # 指定 MMDD，并写入 5 份 HTML
"""
import sys, re, json, base64, math, shutil, importlib.util, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "每日md数据源"


def discover_latest_date():
    candidates = []
    for path in DATA_DIR.glob("10家客户日报_2026*_合并.md"):
        m = re.search(r"10家客户日报_(\d{8})_合并", path.name)
        if m:
            candidates.append(m.group(1)[4:])
    if not candidates:
        raise FileNotFoundError("未找到 10家客户日报_2026MMDD_合并.md")
    return sorted(candidates)[-1]


def parse_target_date(argv):
    for arg in argv[1:]:
        token = arg.strip()
        if token == "write":
            continue
        if re.fullmatch(r"\d{8}", token):
            return token[4:]
        if re.fullmatch(r"\d{4}", token):
            return token
    return discover_latest_date()


DATE = parse_target_date(sys.argv)
YMD = f"2026{DATE}"
MERGED = DATA_DIR / f"10家客户日报_{YMD}_合并.md"
BOARD = DATA_DIR / f"for跑品客户选品门户数据看板{DATE}.md"
INTERNAL_ALL = DATA_DIR / f"内部all-{DATE}.md"

for required in (MERGED, BOARD):
    if not required.exists():
        raise FileNotFoundError(required)

INTERNAL_HTML = [ROOT / "index.html", ROOT / "内部版跑品客户门户.html", ROOT / "内部直客销售版跑品客户门户.html"]
EXTERNAL_HTML = [ROOT / "外部商家客户版跑品客户门户.html", ROOT / "外部商家版发布" / "index.html"]

# ---- 载入解析库 ----
spec = importlib.util.spec_from_file_location("bip", ROOT / "build_internal_portal.py")
bip = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bip)


# ---- PHASE A: 拆分源文件 ----
def split_sources():
    text = MERGED.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    idxs = [i for i, l in enumerate(lines) if re.match(r"^#\s+(.+?)\s+日报\s*$", l)]
    written = []
    for k, i in enumerate(idxs):
        name = re.match(r"^#\s+(.+?)\s+日报\s*$", lines[i]).group(1).strip()
        end = idxs[k + 1] if k + 1 < len(idxs) else len(lines)
        chunk = "".join(lines[i:end]).rstrip() + "\n"
        out = DATA_DIR / f"{name}_日报_{YMD}.md"
        out.write_text(chunk, encoding="utf-8")
        written.append(out.name)
    shutil.copyfile(BOARD, INTERNAL_ALL)
    print(f"[A] 拆分 {len(written)} 个客户日报 + 复制 内部all-{DATE}.md")
    return written


# ---- PHASE B: 构建（增强 overallDelta 解析）----
_ORIG_BUILD_INTERNAL = bip.build_internal


def enhanced_build_internal(path):
    d = _ORIG_BUILD_INTERNAL(path)
    # 强制按文件名取日期（看板正文「数据日期」可能被错写，如0612写成13号）
    mn = re.search(r"内部all-(\d{2})(\d{2})", path.name)
    if mn:
        d["date"] = f"2026-{mn.group(1)}-{mn.group(2)}"
    for link in ("CID", "小店"):
        txt = d.get("overallText", {}).get(link, "") or ""
        md = re.search(r"环比\s*(-?\d+\.?\d*%)", txt)
        wk = re.search(r"周同比\s*(-?\d+\.?\d*%)", txt)
        d.setdefault("overallDelta", {})[link] = {
            "day": md.group(1) if md else "-",
            "week": wk.group(1) if wk else "-",
        }
    return d


def trend_filter(rows):
    out = []
    for r in rows or []:
        dt = str(r.get("日期", "")).strip()
        sp = str(r.get("消耗(万元)", "")).strip()
        if dt in {"05-26", "05-28"} and sp in {"0", "0.0", "0.00", "0.01"}:
            continue
        if dt in {"", "nan"}:
            continue
        out.append(r)
    return out


def build():
    bip.build_internal = enhanced_build_internal  # 让 build_data 使用增强版
    data = bip.build_data()
    for date, bucket in data["byDate"].items():
        for c in bucket.get("clients", []):
            c["trend"] = trend_filter(c.get("trend"))
    return data


# ---- 外部脱敏 ----
def spend_band(v):
    if v is None:
        return v
    v = float(v)
    if v < 0.5:
        return "0到5,000"
    if v < 1.0:
        return "5,000到1万"
    if v < 3.0:
        return "1到3万"
    if v < 5.0:
        return "3到5万"
    return "5万+"


def roi_band(v):
    if v is None:
        return v
    lo = math.floor(float(v) * 10) / 10
    return f"{lo:.1f}到{lo + 0.1:.1f}"


def desensitize(full):
    data = copy.deepcopy(full)
    for date, bucket in data["byDate"].items():
        intern = bucket["internal"]
        new_overview = {}
        for link, rows in intern.get("overview", {}).items():
            nr = []
            for r in rows:
                pct = r.get("消耗占比(%)")
                try:
                    pct = str(int(round(float(pct))))
                except (TypeError, ValueError):
                    pass
                nr.append({"排名": r.get("排名"), "商品二级类目名称V2": r.get("商品二级类目名称V2"), "消耗占比(%)": pct})
            new_overview[link] = nr
        new_products = []
        for p in intern.get("products", []):
            new_products.append({
                "link": p.get("link"), "category": p.get("category"), "rank": p.get("rank"),
                "name": p.get("name"), "spend": spend_band(p.get("spend")),
                "roi": roi_band(p.get("roi")), "url": p.get("url"),
            })
        bucket["internal"] = {
            "date": intern.get("date"), "sourceName": intern.get("sourceName"),
            "overview": new_overview, "products": new_products,
        }
        bucket["sourceFiles"] = []
    return data


# ---- HTML 嵌入 ----
def embed(path, data):
    html = path.read_text(encoding="utf-8")
    m = re.search(r'atob\("([^"]+)"\)', html)
    b64 = base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("ascii")
    new = html[:m.start(1)] + b64 + html[m.end(1):]
    path.write_text(new, encoding="utf-8")


# ---- 部署数据读取（diff用）----
def load_deployed(path):
    html = path.read_text(encoding="utf-8")
    m = re.search(r'atob\("([^"]+)"\)', html)
    return json.loads(base64.b64decode(m.group(1)).decode())


def diff_date(label, new_bucket, old_bucket):
    a = json.dumps(new_bucket, ensure_ascii=False, sort_keys=True)
    b = json.dumps(old_bucket, ensure_ascii=False, sort_keys=True)
    if a == b:
        print(f"   [{label}] 一致 ✓")
        return True
    print(f"   [{label}] 不一致 ✗")
    na, oa = json.loads(a), json.loads(b)
    for key in set(list(na.keys()) + list(oa.keys())):
        sa = json.dumps(na.get(key), ensure_ascii=False, sort_keys=True)
        sb = json.dumps(oa.get(key), ensure_ascii=False, sort_keys=True)
        if sa == sb:
            continue
        if key == "clients":
            ncl = {c.get("name"): c for c in na.get(key, [])}
            ocl = {c.get("name"): c for c in oa.get(key, [])}
            print(f"       clients 名单 new={sorted(ncl)} old={sorted(ocl)}")
            for nm in set(ncl) | set(ocl):
                cn = ncl.get(nm, {})
                co = ocl.get(nm, {})
                for f in set(list(cn.keys()) + list(co.keys())):
                    fa = json.dumps(cn.get(f), ensure_ascii=False, sort_keys=True)
                    fb = json.dumps(co.get(f), ensure_ascii=False, sort_keys=True)
                    if fa != fb:
                        print(f"         客户[{nm}].{f} 不同")
                        print(f"            new={fa[:200]}")
                        print(f"            old={fb[:200]}")
        else:
            print(f"       字段 {key} 不同; new={sa[:160]}")
            print(f"                     old={sb[:160]}")
    return False


def main():
    do_write = "write" in sys.argv[1:]
    split_sources()
    full = build()
    print(f"[B] dates={full['dates']} latest={full['latestDate']}")
    ext = desensitize(full)

    print("[C] 回归 diff（新构建 vs 已部署，针对重叠日期）")
    dep_int = load_deployed(ROOT / "index.html")
    dep_ext = load_deployed(ROOT / "外部商家版发布" / "index.html")
    overlap = [d for d in full["dates"] if d in dep_int.get("byDate", {}) or d in dep_ext.get("byDate", {})]
    if not overlap:
        print("  无重叠日期可 diff")
    for d in overlap:
        if d in full["byDate"] and d in dep_int.get("byDate", {}):
            print(f"  内部 {d}:")
            diff_date(d, full["byDate"][d], dep_int["byDate"][d])
        if d in ext["byDate"] and d in dep_ext.get("byDate", {}):
            print(f"  外部 {d}:")
            diff_date(d, ext["byDate"][d], dep_ext["byDate"][d])

    if do_write:
        for p in INTERNAL_HTML:
            embed(p, full)
            print(f"[D] 写入(内部) {p.name}")
        for p in EXTERNAL_HTML:
            embed(p, ext)
            print(f"[D] 写入(外部) {p.name}")
    else:
        print(f"\n(dry-run，未写HTML。确认diff后用 `python3 _build_0614.py {DATE} write` 写入)")


if __name__ == "__main__":
    main()
