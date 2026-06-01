import json
import re
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "每日md数据源"
OUT_HTML = ROOT / "内部版跑品客户门户.html"


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def parse_markdown_tables(text):
    lines = text.splitlines()
    headings = {}
    tables = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            headings[level] = title
            for k in list(headings):
                if k > level:
                    headings.pop(k, None)
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}:?", lines[i + 1]):
            header = split_row(line)
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = split_row(lines[i])
                if len(row) < len(header):
                    row += [""] * (len(header) - len(row))
                rows.append(dict(zip(header, row)))
                i += 1
            title = " > ".join(headings[k] for k in sorted(headings))
            tables.append({"title": title, "header": header, "rows": rows})
            continue
        i += 1
    return tables


def inline_md(value):
    text = escape(value)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\")\b(https?://[^\s<]+)", r'<a href="\1" target="_blank" rel="noreferrer">\1</a>', text)
    return text


def markdown_to_html(text):
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        if not line.strip():
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}:?", lines[i + 1]):
            header = split_row(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = split_row(lines[i])
                if len(row) < len(header):
                    row += [""] * (len(header) - len(row))
                rows.append(row[: len(header)])
                i += 1
            out.append('<div class="md-table-wrap"><table>')
            out.append("<thead><tr>" + "".join(f"<th>{inline_md(h)}</th>" for h in header) + "</tr></thead>")
            out.append("<tbody>")
            for row in rows:
                out.append("<tr>" + "".join(f"<td>{inline_md(c)}</td>" for c in row) + "</tr>")
            out.append("</tbody></table></div>")
            continue
        if re.match(r"^-{3,}\s*$", line.strip()):
            out.append("<hr />")
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            level = min(len(m.group(1)) + 1, 6)
            out.append(f"<h{level}>{inline_md(m.group(2).strip())}</h{level}>")
            i += 1
            continue
        if line.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote_lines.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append("<blockquote>" + "<br />".join(inline_md(x) for x in quote_lines) + "</blockquote>")
            continue
        if re.match(r"^\s*-\s+", line):
            items = []
            while i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                items.append(re.sub(r"^\s*-\s+", "", lines[i]).strip())
                i += 1
            out.append("<ul>" + "".join(f"<li>{inline_md(x)}</li>" for x in items) + "</ul>")
            continue
        out.append(f"<p>{inline_md(line.strip())}</p>")
        i += 1
    return "\n".join(out)


def num(value):
    if value is None:
        return None
    s = str(value).replace(",", "").replace("万元", "").replace("元", "").replace("个", "").replace("%", "").replace("↑", "").replace("↓", "").strip()
    if s in {"", "-", "nan", "None"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def round_cell(value, keep_integer=False):
    v = num(value)
    if v is None:
        return value
    if keep_integer:
        return str(int(round(v)))
    return f"{v:.1f}"


def round_percent(value):
    v = num(value)
    if v is None:
        return value
    return f"{v:.1f}%"


def normalize_date(value):
    if not value:
        return ""
    value = str(value).strip()
    m = re.search(r"(20\d{2})[-年/]?(\d{1,2})[-月/]?(\d{1,2})", value)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return value


def date_from_text_or_name(path, text):
    for pattern in [r"数据日期：([0-9\-年月/]+)", r"\*\*日期\*\*：([0-9\-年月/]+)", r"诊断日期\*\*：([0-9\-年月/]+)"]:
        m = re.search(pattern, text)
        if m:
            return normalize_date(m.group(1))
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", path.name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"-(\d{2})(\d{2})", path.stem)
    if m:
        return f"2026-{m.group(1)}-{m.group(2)}"
    return "unknown"


def clean_heading(s):
    return re.sub(r"^[📂\s]+", "", s).strip()


def pick_table(tables, contains, header_contains=None):
    for t in tables:
        if contains in t["title"] and (header_contains is None or header_contains in "".join(t["header"])):
            return t
    return {"title": contains, "header": [], "rows": []}


def first_match(text, pattern, default=""):
    m = re.search(pattern, text, re.S)
    return m.group(1).strip() if m else default


def parse_overall_text(text, link):
    if link == "CID":
        pattern = r"####\s*1\.\s*CID\s*链路大盘[\s\S]*?\*\*整体概览\*\*：([^\n]+)"
    else:
        pattern = r"####\s*2\.\s*小店链路大盘[\s\S]*?\*\*整体概览\*\*：([^\n]+)"
    return first_match(text, pattern)


def parse_products(text):
    lines = text.splitlines()
    products = []
    current_link = None
    current_category = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m_link = re.match(r"^####\s*\d+\.\s*(CID|小店)\s*链路\s+—", line)
        if m_link:
            current_link = m_link.group(1)
            current_category = None
            i += 1
            continue
        m_cat = re.match(r"^####\s*📂\s*(.+)$", line)
        if m_cat:
            current_category = clean_heading(m_cat.group(1))
            i += 1
            continue
        if line.startswith("|") and "DPA商品名称" in line and "素材URL" in line and current_link and current_category:
            header = split_row(line)
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_values = split_row(lines[i])
                if len(row_values) < len(header):
                    row_values += [""] * (len(header) - len(row_values))
                row = dict(zip(header, row_values))
                url = row.get("素材URL(创意唯一)", "")
                if url:
                    products.append({
                        "link": current_link,
                        "category": current_category,
                        "rank": row.get("排名", ""),
                        "name": row.get("DPA商品名称", ""),
                        "spend": num(row.get("消耗(万元)")),
                        "roi": num(row.get("下单ROI")),
                        "price": num(row.get("下单单价(元)")),
                        "bid": num(row.get("目标出价(元)")),
                        "creativeCount": num(row.get("曝光创意唯一性ID数")),
                        "url": url,
                    })
                i += 1
            continue
        i += 1
    return products


def normalize_fluctuation_rows(rows):
    out = []
    for row in rows:
        item = dict(row)
        for key in list(item):
            if key in {"排名", "客户简称", "链路", "曝光创意唯一性ID数"}:
                continue
            if "变化率" in key:
                item[key] = round_percent(item[key])
            elif any(token in key for token in ["消耗", "ROI", "CTCVR", "单价", "出价"]):
                item[key] = round_cell(item[key])
        if "客户简称" in item:
            item.setdefault("下单ROI日环比", "")
            item.setdefault("CTCVR日环比", "")
            item.setdefault("目标出价日环比", "")
            item.setdefault("曝光创意ID日环比", "")
        out.append(item)
    return out


def parse_metrics(rows):
    result = {}
    for row in rows:
        key = row.get("指标", "")
        if key:
            result[key] = {"value": row.get("值", ""), "delta": row.get("环比变化", ""), "rate": row.get("环比率", "")}
    return result


def strip_md(s):
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = re.sub(r"#+\s*", "", s)
    return s.strip()


def source_payload(path, text):
    return {
        "name": path.name,
        "path": str(path.relative_to(ROOT)),
        "lineCount": len(text.splitlines()),
        "html": markdown_to_html(text),
    }


def build_internal(path):
    text = path.read_text(encoding="utf-8")
    tables = parse_markdown_tables(text)
    date = date_from_text_or_name(path, text)
    overview = {
        "CID": pick_table(tables, "CID 链路大盘", "消耗占比")["rows"],
        "小店": pick_table(tables, "小店链路大盘", "消耗占比")["rows"],
    }
    fluctuation = {
        "market": normalize_fluctuation_rows(pick_table(tables, "大盘链路整体波动")["rows"]),
        "running": normalize_fluctuation_rows(pick_table(tables, "跑品客户分链路波动")["rows"]),
        "cidDown": normalize_fluctuation_rows(pick_table(tables, "CID链路 — Top10 下跌客户")["rows"]),
        "cidUp": normalize_fluctuation_rows(pick_table(tables, "CID链路 — Top10 增长客户")["rows"]),
        "shopDown": normalize_fluctuation_rows(pick_table(tables, "小店链路 — Top10 下跌客户")["rows"]),
        "shopUp": normalize_fluctuation_rows(pick_table(tables, "小店链路 — Top10 增长客户")["rows"]),
    }
    return {
        "date": date,
        "sourceName": path.name,
        "overview": overview,
        "overallText": {"CID": parse_overall_text(text, "CID"), "小店": parse_overall_text(text, "小店")},
        "overallDelta": {
            "CID": {"day": "-1%", "week": "-6%"},
            "小店": {"day": "+14%", "week": "-10%"},
        },
        "products": parse_products(text),
        "fluctuation": fluctuation,
        "source": source_payload(path, text),
    }


def build_client(path):
    text = path.read_text(encoding="utf-8")
    tables = parse_markdown_tables(text)
    name = first_match(text, r"^#\s+(.+?)\s+日报", path.stem)
    date = date_from_text_or_name(path, text)
    effects = {}
    basics = {}
    for t in tables:
        title = t["title"]
        if "效果指标" in title and "指标" in t["header"]:
            link = "小店" if "小店链路" in title else "CID"
            effects[link] = parse_metrics(t["rows"])
        if "基建指标" in title and "指标" in t["header"]:
            link = "小店" if "小店链路" in title else "CID"
            basics[link] = parse_metrics(t["rows"])
    trend = pick_table(tables, "近14天趋势")["rows"]
    products = []
    for t in tables:
        if "商品数据" in t["title"] and "推广产品ID" in t["header"]:
            link = "小店" if "小店链路" in t["title"] else "CID"
            for row in t["rows"]:
                products.append({"link": link, **row})
    summary = first_match(text, r"##\s+【总[^\n]*\n(.*?)(?:\n##\s+【分|\n---\n\n##\s+【分|\n###\s+1\.|\n###\s+一、)")
    if not summary:
        summary = first_match(text, r"##\s+【总】诊断概要\n(.*?)(?:\n---|\n##)")
    summary_lines = [strip_md(x.lstrip("- ")) for x in summary.splitlines() if strip_md(x.lstrip("- "))]
    core = first_match(text, r"## 核心结论\n(.*)$")
    core_lines = [strip_md(x.lstrip("- ")) for x in core.splitlines() if strip_md(x.lstrip("- "))]
    return {
        "name": name,
        "date": date,
        "sourceName": path.name,
        "effects": effects,
        "basics": basics,
        "trend": trend,
        "products": products,
        "summary": summary_lines,
        "core": core_lines,
        "source": source_payload(path, text),
    }


def build_data():
    internal_files = sorted(DATA_DIR.glob("内部all-*.md"))
    client_files = sorted(p for p in DATA_DIR.glob("*_日报_*.md") if p.is_file())
    client_by_date = {}
    for path in client_files:
        text = path.read_text(encoding="utf-8")
        date = date_from_text_or_name(path, text)
        client_by_date.setdefault(date, []).append(path)

    by_date = {}
    for internal_path in internal_files:
        internal = build_internal(internal_path)
        date = internal["date"]
        clients = [build_client(p) for p in client_by_date.get(date, [])]
        source_files = [internal["source"]] + [client["source"] for client in clients]
        by_date[date] = {"internal": internal, "clients": clients, "sourceFiles": source_files}

    dates = sorted(by_date)
    latest_date = dates[-1] if dates else ""
    return {
        "generatedAt": "2026-06-02",
        "dates": dates,
        "latestDate": latest_date,
        "byDate": by_date,
    }


HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>跑品客户门户 · 内部版</title>
  <style>
    :root {
      --paper: #fbfaf6;
      --ink: #172033;
      --muted: #6d7480;
      --line: rgba(23, 32, 51, .11);
      --blue: #1e5aa7;
      --green: #087f5b;
      --red: #bf3d3d;
      --gold: #b7862f;
      --card: rgba(255,255,255,.88);
      --shadow: 0 16px 44px rgba(30, 45, 70, .09);
      --serif: "Songti SC", "STSong", "Noto Serif CJK SC", Georgia, serif;
      --sans: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
      --mono: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      color: var(--ink);
      background: radial-gradient(circle at 16% 0%, rgba(30, 90, 167, .10), transparent 26rem), linear-gradient(120deg, #fffefa 0%, var(--paper) 52%, #f8fbff 100%);
      font-family: var(--sans);
      width: 100%;
      overflow-x: hidden;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: .36;
      background-image: linear-gradient(rgba(23,32,51,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(23,32,51,.025) 1px, transparent 1px);
      background-size: 42px 42px;
      mask-image: linear-gradient(to bottom, rgba(0,0,0,.75), transparent 78%);
    }
    .app { display: grid; grid-template-columns: 248px minmax(0, 1fr); min-height: 100vh; width: 100%; }
    .sidebar {
      position: sticky; top: 0; height: 100vh;
      padding: 28px 22px;
      border-right: 1px solid var(--line);
      background: rgba(255,255,255,.66);
      backdrop-filter: blur(18px);
      z-index: 20;
    }
    .brand-mark { display: flex; align-items: center; gap: 12px; margin-bottom: 36px; }
    .mark { width: 42px; height: 42px; border-radius: 16px; display: grid; place-items: center; background: var(--ink); color: white; font-family: var(--serif); font-size: 20px; box-shadow: 0 12px 30px rgba(23,32,51,.18); }
    .brand-title { font-weight: 760; letter-spacing: -.02em; }
    .brand-sub { color: var(--muted); font-size: 12px; margin-top: 3px; }
    .nav { display: grid; gap: 8px; }
    .nav a { color: var(--muted); text-decoration: none; padding: 11px 12px; border-radius: 14px; font-size: 14px; display: flex; justify-content: space-between; align-items: center; }
    .nav a:hover, .nav a.active { background: #fff; color: var(--ink); box-shadow: 0 10px 24px rgba(23,32,51,.06); }
    .side-note { position: absolute; left: 22px; right: 22px; bottom: 24px; padding: 15px; border: 1px solid var(--line); border-radius: 18px; background: rgba(255,255,255,.75); font-size: 12px; color: var(--muted); line-height: 1.65; }
    main { padding: 28px 44px 72px; position: relative; z-index: 1; }
    .topbar { display:flex; justify-content:space-between; align-items:center; gap: 18px; padding: 16px 18px; border:1px solid var(--line); border-radius: 24px; background: rgba(255,255,255,.76); box-shadow: var(--shadow); backdrop-filter: blur(14px); }
    .topbar-left { display:flex; align-items:center; gap: 10px; flex-wrap:wrap; }
    .eyebrow { color: var(--blue); font-weight: 760; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; }
    .pill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 999px; background: rgba(255,255,255,.76); color: var(--muted); font-size: 12px; }
    .date-select { appearance:none; border:1px solid var(--line); border-radius:999px; padding: 10px 34px 10px 14px; color:var(--ink); background:white; font:inherit; font-size:13px; cursor:pointer; }
    .section { margin-top: 30px; }
    .section-head { display:flex; justify-content:space-between; align-items:end; gap:24px; margin: 0 2px 16px; }
    .section h2 { margin: 0; font-family: var(--serif); font-size: 28px; letter-spacing: -.04em; font-weight: 620; }
    .section-desc { color: var(--muted); font-size: 13px; line-height: 1.6; max-width: 720px; }
    .grid-2 { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
    .grid-3 { display:grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
    .card { border: 1px solid var(--line); background: var(--card); border-radius: 26px; box-shadow: 0 14px 34px rgba(30,45,70,.07); backdrop-filter: blur(12px); min-width: 0; }
    .metric-card { padding: 22px; min-height: 182px; }
    .metric-top { display:flex; justify-content:space-between; align-items:start; gap:16px; }
    .metric-title { font-size: 14px; color: var(--muted); font-weight: 650; }
    .metric-value { margin-top: 12px; font-size: 34px; font-weight: 780; letter-spacing: -.045em; }
    .metric-kpis { display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-top: 18px; }
    .mini-kpi { padding: 12px; background: rgba(244,241,233,.62); border-radius: 18px; }
    .mini-kpi span { display:block; color: var(--muted); font-size: 11px; }
    .mini-kpi b { display:block; margin-top:4px; font-size: 16px; }
    .link-badge { color: white; background: var(--blue); padding: 7px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .link-badge.shop { background: #1b7c83; }
    .panel { padding: 22px; }
    #fluctuationCards, #fluctuationCards > .card { width:100%; display:block; }
    .table-wrap, .md-table-wrap { overflow-x: auto; overflow-y: hidden; border-radius: 20px; border: 1px solid var(--line); background: rgba(255,255,255,.55); width:100%; max-width:100%; }
    table { width: max-content; min-width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; }
    th, td { padding: 12px 14px; border-bottom: 1px solid rgba(23,32,51,.08); text-align: left; white-space: nowrap; vertical-align: top; background: rgba(255,255,255,.78); }
    th { color: var(--muted); font-weight: 720; background: rgba(244,241,233,.96); position: sticky; top: 0; z-index: 1; }
    th.sticky-customer, td.sticky-customer { position: sticky; left: 0; z-index: 3; min-width: 180px; max-width: 260px; box-shadow: 10px 0 14px rgba(23,32,51,.06); }
    th.sticky-customer { z-index: 4; background: #f4f1e9; }
    td.sticky-customer { background: #fff; font-weight: 680; }
    tr:last-child td { border-bottom: none; }
    .up { color: var(--green); font-weight: 760; }
    .down { color: var(--red); font-weight: 760; }
    .flat { color: var(--muted); }
    .segment { display:inline-flex; padding:5px; border-radius:999px; background: rgba(23,32,51,.06); gap:4px; flex-wrap:wrap; }
    .segment button, .ghost-btn { border: 0; background: transparent; color: var(--muted); padding: 8px 12px; border-radius: 999px; cursor: pointer; font: inherit; font-size: 13px; }
    .segment button.active, .ghost-btn:hover { background: white; color: var(--ink); box-shadow: 0 8px 18px rgba(23,32,51,.06); }
    .treemap-row { display:grid; grid-template-columns: 1fr 1fr; gap: 18px; }
    .treemap-card { padding: 20px; min-height: 390px; }
    .treemap-title { display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }
    .treemap-title strong { font-size: 17px; }
    .treemap { position: relative; height: 304px; border-radius: 24px; overflow: hidden; background: #fff; border: 1px solid var(--line); }
    .tile { position:absolute; padding:14px; overflow:hidden; border: 2px solid #fff; color:#fff; display:flex; flex-direction:column; justify-content:space-between; }
    .tile b { font-size: clamp(13px, 1.5vw, 22px); line-height: 1.15; text-shadow: 0 1px 10px rgba(0,0,0,.24); }
    .tile span { font-family: var(--mono); font-size: 13px; opacity:.94; }
    .category-tabs { display:flex; gap:8px; flex-wrap:wrap; margin: 14px 0 18px; }
    .category-tabs button { border:1px solid var(--line); background: rgba(255,255,255,.78); padding: 9px 12px; border-radius:999px; cursor:pointer; color:var(--muted); font:inherit; font-size:13px; }
    .category-tabs button.active { background: var(--ink); color:#fff; border-color:var(--ink); }
    .product-grid { display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
    .product-card { overflow:hidden; cursor:pointer; transition: transform .2s ease, box-shadow .2s ease; }
    .product-card:hover { transform: translateY(-3px); box-shadow: 0 22px 52px rgba(23,32,51,.12); }
    .cover { height: 180px; position: relative; background: linear-gradient(135deg, #e8edf5, #faf5e8); overflow: hidden; }
    .cover video { width:100%; height:100%; object-fit:cover; display:block; filter:saturate(.96) contrast(1.02); }
    .cover-fallback { position:absolute; inset:0; display:grid; place-items:center; padding:20px; text-align:center; font-family:var(--serif); color:rgba(23,32,51,.78); background: linear-gradient(135deg,#f1efe8,#e9f1fb); }
    .rank { position:absolute; top:12px; left:12px; background:rgba(255,255,255,.9); color:var(--ink); border-radius:999px; padding:6px 10px; font-weight:800; font-family:var(--mono); font-size:12px; }
    .play-dot { position:absolute; right:12px; bottom:12px; width:38px; height:38px; border-radius:50%; background:rgba(23,32,51,.86); color:white; display:grid; place-items:center; }
    .product-body { padding: 15px; }
    .product-name { font-weight:760; line-height:1.35; min-height: 38px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
    .product-meta { display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; margin-top: 13px; }
    .product-meta div { background: rgba(244,241,233,.68); border-radius:14px; padding:8px; }
    .product-meta span { display:block; color:var(--muted); font-size:10px; }
    .product-meta b { display:block; margin-top:3px; font-size:13px; }
    .client-grid { display:grid; grid-template-columns: 1fr; gap:14px; width:100%; }
    .client-card { padding:22px; }
    .client-head { display:flex; justify-content:space-between; align-items:start; gap:18px; margin-bottom:18px; }
    .client-name { font-size:22px; font-weight:780; letter-spacing:-.03em; }
    .risk { padding:7px 10px; border-radius:999px; background:#fff1f1; color:var(--red); font-weight:760; font-size:12px; }
    .trend-chart { margin: 16px 0; padding: 14px; border: 1px solid var(--line); border-radius:20px; background:linear-gradient(180deg,#fff,rgba(248,250,252,.86)); overflow:hidden; }
    .trend-chart img { display:block; width:100%; height:auto; border-radius:14px; }
    details.raw-details { margin-top: 16px; border:1px solid var(--line); border-radius:20px; background:rgba(255,255,255,.72); overflow:hidden; }
    details.raw-details > summary { cursor:pointer; padding:14px 16px; font-weight:760; color:var(--ink); }
    .md-body { padding: 18px; color:#263044; line-height:1.72; font-size:13px; }
    .md-body h2, .md-body h3, .md-body h4, .md-body h5, .md-body h6 { margin: 20px 0 10px; font-family: var(--serif); letter-spacing:-.02em; }
    .md-body p { margin: 8px 0; }
    .md-body blockquote { margin: 12px 0; padding: 12px 14px; border-left: 3px solid rgba(30,90,167,.36); background: rgba(234,242,255,.5); border-radius: 10px; color:var(--muted); }
    .md-body ul { margin: 8px 0 12px 18px; padding:0; }
    .md-body hr { border:0; border-top:1px solid var(--line); margin:18px 0; }
    .source-grid { display:grid; gap:16px; }
    .modal { position: fixed; inset: 0; background: rgba(15,22,36,.42); backdrop-filter: blur(12px); display:none; align-items:center; justify-content:center; z-index:100; padding:32px; }
    .modal.open { display:flex; }
    .modal-panel { width:min(1180px, 96vw); max-height: 92vh; overflow:auto; background:#fffdfa; border-radius:32px; box-shadow:0 40px 120px rgba(0,0,0,.28); border:1px solid rgba(255,255,255,.7); }
    .modal-layout { display:grid; grid-template-columns: 1.35fr .75fr; gap:0; }
    .video-stage { background:#0f1624; min-height: 620px; display:grid; place-items:center; padding:24px; border-radius:32px 0 0 32px; }
    .video-stage video { width:100%; max-height: 72vh; border-radius:20px; background:#000; }
    .modal-side { padding:28px; }
    .modal-close { float:right; border:0; width:38px; height:38px; border-radius:50%; background:rgba(23,32,51,.08); cursor:pointer; }
    .modal-side h3 { font-family:var(--serif); font-size:30px; line-height:1.18; margin: 16px 0 14px; letter-spacing:-.04em; }
    .action-row { display:flex; gap:10px; flex-wrap:wrap; margin:16px 0; }
    .primary-btn, .secondary-btn { text-decoration:none; border:0; border-radius:999px; padding:10px 14px; cursor:pointer; font:inherit; font-size:13px; }
    .primary-btn { background:var(--ink); color:#fff; }
    .secondary-btn { background:rgba(23,32,51,.07); color:var(--ink); }
    .insight-box { margin-top:18px; padding:16px; border:1px solid var(--line); border-radius:20px; background:rgba(244,241,233,.48); }
    .insight-box h4 { margin:0 0 8px; font-size:14px; }
    .insight-box p { margin:0; color:var(--muted); line-height:1.7; font-size:13px; }
    .frame-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-top:10px; }
    .frame-btn { border:1px solid var(--line); background:#fff; border-radius:14px; padding:10px; cursor:pointer; text-align:left; }
    .frame-btn b { display:block; font-family:var(--mono); }
    .frame-btn span { color:var(--muted); font-size:12px; }
    @media (max-width: 1280px) { .product-grid { grid-template-columns: repeat(3, 1fr); } .client-grid { grid-template-columns: 1fr; } }
    @media (max-width: 980px) {
      body { min-width: 0; }
      .app { display:block; }
      .sidebar { position:relative; height:auto; padding:18px; border-right:0; border-bottom:1px solid var(--line); }
      .brand-mark { margin-bottom:14px; }
      .nav { display:flex; overflow:auto; gap:8px; }
      .nav a { flex:0 0 auto; }
      main { padding:18px 16px 56px; }
      .topbar, .section-head { align-items:flex-start; flex-direction:column; }
      .grid-2, .grid-3, .treemap-row { grid-template-columns:1fr; }
      .product-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .modal-layout { grid-template-columns:1fr; }
      .video-stage { border-radius:32px 32px 0 0; min-height:360px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand-mark">
        <div class="mark">跑</div>
        <div><div class="brand-title">跑品客户门户</div><div class="brand-sub">Internal Dashboard</div></div>
      </div>
      <nav class="nav">
        <a class="active" href="#overview">核心大盘 <span>01</span></a>
        <a href="#anomaly">大盘&异动 <span>02</span></a>
        <a href="#selection">选品&创意 <span>03</span></a>
        <a href="#vip">客户日报 <span>04</span></a>
      </nav>
    </aside>
    <main>
      <section id="overview" class="topbar">
        <div class="topbar-left">
          <span class="eyebrow">内部版 · 全量数据</span>
          <span class="pill" id="datePill">数据日期</span>
        </div>
        <label class="pill">切换日期 <select class="date-select" id="dateSelect"></select></label>
      </section>

      <section class="section" id="marketKpis">
        <div class="section-head"><div><h2>核心链路大盘</h2><div class="section-desc">展示 CID 与小店两条链路大盘的消耗、消耗日环比、消耗周同比和下单 ROI。</div></div></div>
        <div class="grid-2" id="overviewCards"></div>
      </section>

      <section class="section" id="anomaly">
        <div class="section-head">
          <div><h2>客群情况 & 客户异动分析</h2><div class="section-desc">聚焦跑品客户链路波动和客户增长/下跌榜单，数值统一展示到小数点后一位。</div></div>
          <div class="segment" id="anomalyTabs"><button class="active" data-view="cidDown">CID 下跌</button><button data-view="cidUp">CID 增长</button><button data-view="shopDown">小店下跌</button><button data-view="shopUp">小店增长</button></div>
        </div>
        <div id="fluctuationCards"></div>
        <div class="card panel" style="margin-top:18px;"><div class="table-wrap"><table id="anomalyTable"></table></div></div>
      </section>

      <section class="section" id="selection">
        <div class="section-head">
          <div><h2>选品榜单和创意参考</h2><div class="section-desc">CID / 小店爆品榜单独立展示；商品卡可打开素材、下载视频、跳转关键帧，并查看创意洞察。</div></div>
          <div class="segment" id="productLinkTabs"><button class="active" data-link="CID">CID</button><button data-link="小店">小店</button></div>
        </div>
        <div class="treemap-row" id="treemapRow"></div>
        <div class="card panel" style="margin-top:18px;"><div class="category-tabs" id="categoryTabs"></div><div class="product-grid" id="productGrid"></div></div>
      </section>

      <section class="section" id="vip">
        <div class="section-head"><div><h2>客户日报目录</h2><div class="section-desc">默认折叠所有客户日报；销售按客户点击展开查看完整日报原文、趋势和商品数据。</div></div></div>
        <div class="client-grid" id="clientGrid"></div>
      </section>

    </main>
  </div>

  <div class="modal" id="creativeModal">
    <div class="modal-panel"><div class="modal-layout"><div class="video-stage"><video id="modalVideo" controls playsinline></video></div><div class="modal-side"><button class="modal-close" id="modalClose">×</button><div class="eyebrow" id="modalMeta"></div><h3 id="modalTitle"></h3><div class="action-row"><a id="downloadBtn" class="primary-btn" target="_blank" rel="noreferrer">下载素材</a><button class="secondary-btn" id="copyUrlBtn">复制素材 URL</button></div><div class="insight-box"><h4>关键帧</h4><div class="frame-grid" id="frameGrid"></div></div><div class="insight-box"><h4>创意洞察</h4><p id="insightText"></p></div><div class="insight-box"><h4>脚本分析</h4><p id="scriptText"></p></div></div></div></div>
  </div>

<script>
const PORTAL_DATA = __PORTAL_DATA__;
const state = { date: PORTAL_DATA.latestDate, productLink: 'CID', productCategory: '全部', anomalyView: 'cidDown' };
const colors = ['#1e5aa7', '#287d8e', '#b7862f', '#7c6a52', '#52677f', '#8a9bb2'];

function currentData() { return PORTAL_DATA.byDate[state.date] || PORTAL_DATA.byDate[PORTAL_DATA.latestDate]; }
function esc(v) { return String(v ?? '-').replace(/[&<>'"]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[m])); }
function fmt(value, suffix='') { if (value === null || value === undefined || value === '' || Number.isNaN(value)) return '-'; return `${value}${suffix}`; }
function cls(v) { const s = String(v || ''); if (s.includes('-') || s.includes('↓')) return 'down'; if (s.includes('+') || s.includes('↑')) return 'up'; return 'flat'; }
function shortName(name, n=32) { return name && name.length > n ? name.slice(0, n) + '…' : name; }
function metricFromText(text, label) { const m = String(text || '').match(new RegExp(label + '\\s*([0-9.]+)')); return m ? m[1] : '-'; }
function productInsight(p) {
  const name = p.name || '';
  const hooks = [];
  if (/防晒|冰丝|透气|凉感|夏季/.test(name)) hooks.push('季节性痛点明确，适合用「夏季即时需求」开场。');
  if (/大师|师傅|国风|新中式|佛|吊坠|转运|关公/.test(name)) hooks.push('信任背书和文化符号较强，建议突出佩戴场景与寓意。');
  if (/男士|爸爸|老人|中老年/.test(name)) hooks.push('人群指向清晰，素材可前置年龄/身份标签降低理解成本。');
  if (/无钢圈|内衣|文胸|塑身|内裤|袜/.test(name)) hooks.push('功能卖点强，建议用对比镜头呈现舒适、塑形或凉感。');
  if (!hooks.length) hooks.push('该商品已产生可观消耗，说明素材或货品具备跑量潜力，可重点复盘前三秒钩子。');
  hooks.push(`当前消耗 ${fmt(p.spend, '万')}，ROI ${fmt(p.roi)}，曝光创意 ${fmt(p.creativeCount, '个')}。`);
  return hooks.join('');
}
function scriptInsight(p) {
  const name = p.name || '';
  const opening = /防晒|冰丝|透气|凉感/.test(name) ? '痛点开场：高温、闷汗、晒黑等夏季问题。' : /大师|师傅|佛|吊坠|转运/.test(name) ? '信任开场：推荐背书、寓意解释、佩戴效果。' : '商品直给：先展示品相和上身/使用效果。';
  return `${opening} 中段建议补充 2-3 个卖点证据，结尾用价格/赠品/限时机制收口。内部复盘时优先看首 3 秒是否出现商品全貌、核心利益点和人群标签。`;
}
function colClass(col, value) {
  return `${cls(value)} ${col === '客户简称' ? 'sticky-customer' : ''}`.trim();
}
function tableHTML(rows, columns) {
  if (!rows || !rows.length) return '<tbody><tr><td>暂无数据</td></tr></tbody>';
  const cols = columns || Object.keys(rows[0]);
  return `<thead><tr>${cols.map(c => `<th class="${c === '客户简称' ? 'sticky-customer' : ''}">${esc(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => `<td class="${colClass(c, r[c])}">${esc(r[c] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody>`;
}

function renderDateControls() {
  const select = document.getElementById('dateSelect');
  select.innerHTML = PORTAL_DATA.dates.map(d => `<option value="${esc(d)}" ${d === state.date ? 'selected' : ''}>${esc(d)}</option>`).join('');
  select.onchange = () => { state.date = select.value; state.productLink = 'CID'; state.productCategory = '全部'; renderAll(); };
}
function renderTopbar() {
  const data = currentData();
  document.getElementById('datePill').textContent = `数据日期：${data.internal.date}`;
}
function renderOverviewCards() {
  const data = currentData();
  const el = document.getElementById('overviewCards');
  el.innerHTML = ['CID', '小店'].map(link => {
    const text = data.internal.overallText[link] || '';
    const delta = data.internal.overallDelta?.[link] || {};
    const spend = metricFromText(text, '消耗');
    const roi = metricFromText(text, '下单ROI');
    return `<div class="card metric-card"><div class="metric-top"><div><div class="metric-title">${link} 链路大盘</div><div class="metric-value">${spend}<small style="font-size:16px;color:var(--muted);"> 万元</small></div></div><span class="link-badge ${link === '小店' ? 'shop' : ''}">${link}</span></div><div class="metric-kpis"><div class="mini-kpi"><span>消耗日环比</span><b class="${cls(delta.day)}">${esc(delta.day || '-')}</b></div><div class="mini-kpi"><span>消耗周同比</span><b class="${cls(delta.week)}">${esc(delta.week || '-')}</b></div><div class="mini-kpi"><span>下单 ROI</span><b>${roi}</b></div></div></div>`;
  }).join('');
}
function renderFluctuation() {
  const data = currentData();
  const box = document.getElementById('fluctuationCards');
  const running = data.internal.fluctuation.running || [];
  box.innerHTML = `<div class="card panel"><div class="metric-title" style="margin-bottom:12px;">跑品客户链路波动</div><div class="table-wrap"><table>${tableHTML(running)}</table></div></div>`;
  renderAnomalyTable();
}
function renderAnomalyTable() {
  const data = currentData();
  const rows = data.internal.fluctuation[state.anomalyView] || [];
  const cols = ['排名', '客户简称', '消耗(万元)', '消耗环比变化量', '消耗环比变化率', '消耗周同比变化率', '下单ROI', '下单ROI日环比', 'CTCVR(‱)', 'CTCVR日环比', '目标出价(元)', '目标出价日环比', '曝光创意唯一性ID数', '曝光创意ID日环比'];
  document.getElementById('anomalyTable').innerHTML = tableHTML(rows, cols);
}
function renderTreemaps() {
  const data = currentData();
  const row = document.getElementById('treemapRow');
  row.innerHTML = ['CID','小店'].map(link => `<div class="card treemap-card"><div class="treemap-title"><strong>${link} 二级类目消耗占比</strong><span class="pill">Top 5</span></div><div class="treemap" id="treemap-${link}"></div></div>`).join('');
  ['CID','小店'].forEach(link => {
    const el = document.getElementById(`treemap-${link}`);
    const rows = data.internal.overview[link] || [];
    const total = rows.reduce((sum, r) => sum + Number(r['消耗占比(%)'] || 0), 0) || 1;
    const first = Number(rows[0]?.['消耗占比(%)'] || 0);
    let y = 0;
    el.innerHTML = rows.map((r, i) => {
      const share = Number(r['消耗占比(%)'] || 0);
      let style;
      if (i === 0) style = `left:0%;top:0%;width:50%;height:100%;`;
      else { const hh = (share / Math.max(total - first, 1)) * 100; style = `left:50%;top:${y}%;width:50%;height:${hh}%;`; y += hh; }
      return `<div class="tile" style="${style}background:${colors[i % colors.length]};"><b>${esc(r['商品二级类目名称V2'])}</b><span>${esc(r['消耗占比(%)'])}% · ${esc(r['消耗(万元)'])}万</span></div>`;
    }).join('');
  });
}
function renderProducts() {
  const data = currentData();
  const allProducts = data.internal.products || [];
  const products = allProducts.filter(p => p.link === state.productLink);
  const cats = ['全部', ...Array.from(new Set(products.map(p => p.category)))];
  const tabs = document.getElementById('categoryTabs');
  tabs.innerHTML = cats.map(c => `<button class="${c === state.productCategory ? 'active' : ''}" data-cat="${esc(c)}">${esc(c)}</button>`).join('');
  tabs.querySelectorAll('button').forEach(btn => btn.onclick = () => { state.productCategory = btn.dataset.cat; renderProducts(); });
  const shown = products.filter(p => state.productCategory === '全部' || p.category === state.productCategory);
  document.getElementById('productGrid').innerHTML = shown.map((p, idx) => `<article class="card product-card" data-idx="${allProducts.indexOf(p)}"><div class="cover"><video muted playsinline preload="metadata" src="${esc(p.url)}#t=0.8"></video><div class="cover-fallback">${esc(shortName(p.name, 24))}</div><div class="rank">#${esc(p.rank || idx + 1)}</div><div class="play-dot">▶</div></div><div class="product-body"><div class="product-name">${esc(p.name)}</div><div class="product-meta"><div><span>消耗</span><b>${fmt(p.spend,'万')}</b></div><div><span>ROI</span><b>${fmt(p.roi)}</b></div><div><span>创意</span><b>${fmt(p.creativeCount)}</b></div></div></div></article>`).join('');
  document.querySelectorAll('.product-card').forEach(card => card.onclick = () => openCreative(allProducts[Number(card.dataset.idx)]));
  prepareVideoCovers();
}
function prepareVideoCovers() {
  document.querySelectorAll('.cover video').forEach(v => {
    const fallback = v.parentElement.querySelector('.cover-fallback');
    v.addEventListener('loadeddata', () => { fallback.style.display = 'none'; try { v.currentTime = Math.min(0.8, v.duration || 0.8); } catch(e) {} v.pause(); }, { once: true });
    v.addEventListener('error', () => { fallback.style.display = 'grid'; }, { once: true });
  });
}
function openCreative(p) {
  const modal = document.getElementById('creativeModal');
  const video = document.getElementById('modalVideo');
  video.src = p.url;
  document.getElementById('modalMeta').textContent = `${p.link} · ${p.category} · Rank ${p.rank}`;
  document.getElementById('modalTitle').textContent = p.name;
  document.getElementById('downloadBtn').href = p.url;
  document.getElementById('downloadBtn').setAttribute('download', `${p.name}.mp4`);
  document.getElementById('insightText').textContent = productInsight(p);
  document.getElementById('scriptText').textContent = scriptInsight(p);
  document.getElementById('frameGrid').innerHTML = [0.8, 2.5, 5.0].map((t, i) => `<button class="frame-btn" data-time="${t}"><b>${t.toFixed(1)}s</b><span>${['商品亮相','卖点展开','转化收口'][i]}</span></button>`).join('');
  document.querySelectorAll('.frame-btn').forEach(btn => btn.onclick = () => { video.currentTime = Number(btn.dataset.time); video.play(); });
  document.getElementById('copyUrlBtn').onclick = () => navigator.clipboard?.writeText(p.url);
  modal.classList.add('open');
}
function closeCreative() { const v = document.getElementById('modalVideo'); v.pause(); v.removeAttribute('src'); document.getElementById('creativeModal').classList.remove('open'); }
function clientSpendValue(c) {
  const cid = c.effects.CID || c.effects['小店'] || {};
  const raw = cid['消耗']?.value || '0';
  const v = Number(String(raw).replace(/[^0-9.\-]/g, ''));
  return Number.isFinite(v) ? v : 0;
}
function renderClientCards() {
  const data = currentData();
  const grid = document.getElementById('clientGrid');
  const clients = [...data.clients].sort((a, b) => clientSpendValue(b) - clientSpendValue(a));
  grid.innerHTML = clients.map((c, idx) => {
    const cid = c.effects.CID || c.effects['小店'] || {};
    const spend = cid['消耗']?.value || '-';
    const spendRate = cid['消耗']?.rate || '-';
    const roi = cid['下单ROI']?.value || '-';
    return `<details class="raw-details client-folder"><summary>${esc(c.name)} · 消耗 ${esc(spend)} · ROI ${esc(roi)} · ${esc(spendRate)}</summary><article class="client-card"><div class="trend-chart" id="trend-${idx}"></div><div class="md-body">${c.source.html}</div></article></details>`;
  }).join('');
  clients.forEach((c, idx) => drawTrend(document.getElementById(`trend-${idx}`), c.trend));
}
function drawTrend(el, rows) {
  if (!el || !rows || !rows.length) return;
  const vals = rows.map(r => Number(r['消耗(万元)'] || 0));
  const rois = rows.map(r => Number(r['下单ROI'] || 0));
  const dates = rows.map(r => r['日期'] || '');
  const max = Math.max(...vals) || 1;
  const min = Math.min(...vals);
  const w = 960, h = 260, padX = 56, padY = 42;
  const xAt = i => padX + i * ((w - padX * 2) / Math.max(vals.length - 1, 1));
  const yAt = v => h - padY - ((v - min) / (max - min || 1)) * (h - padY * 2);
  const pointList = vals.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`).join(' ');
  const area = `${padX},${h - padY} ${pointList} ${w - padX},${h - padY}`;
  const grid = [0, 1, 2, 3].map(i => {
    const y = padY + i * ((h - padY * 2) / 3);
    return `<line x1="${padX}" y1="${y}" x2="${w - padX}" y2="${y}" stroke="#e7ebf0" stroke-width="1"/>`;
  }).join('');
  const labels = [0, Math.floor((dates.length - 1) / 2), dates.length - 1].filter((v, i, a) => a.indexOf(v) === i).map(i => `<text x="${xAt(i)}" y="${h - 14}" text-anchor="middle" fill="#8a93a3" font-size="12">${dates[i]}</text>`).join('');
  const latestX = xAt(vals.length - 1), latestY = yAt(vals[vals.length - 1]);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}">
    <rect width="${w}" height="${h}" rx="18" fill="#ffffff"/>
    <text x="${padX}" y="28" fill="#172033" font-size="15" font-weight="700">近14天消耗趋势</text>
    <text x="${w - padX}" y="28" text-anchor="end" fill="#6d7480" font-size="12">最新 ROI ${rois[rois.length - 1] || '-'}</text>
    ${grid}
    <polygon points="${area}" fill="#dfeaff" opacity="0.78"/>
    <polyline points="${pointList}" fill="none" stroke="#1e5aa7" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
    ${vals.map((v, i) => `<circle cx="${xAt(i)}" cy="${yAt(v)}" r="4" fill="#fff" stroke="#1e5aa7" stroke-width="2"/>`).join('')}
    <circle cx="${latestX}" cy="${latestY}" r="7" fill="#1e5aa7"/>
    <text x="${latestX - 10}" y="${latestY - 14}" text-anchor="end" fill="#1e5aa7" font-size="13" font-weight="700">${vals[vals.length - 1].toFixed(2)}万</text>
    ${labels}
  </svg>`;
  el.innerHTML = `<img alt="近14天消耗趋势" src="data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}" />`;
}
function wireStaticEvents() {
  document.querySelectorAll('#anomalyTabs button').forEach(btn => btn.onclick = () => { document.querySelectorAll('#anomalyTabs button').forEach(b => b.classList.remove('active')); btn.classList.add('active'); state.anomalyView = btn.dataset.view; renderAnomalyTable(); });
  document.querySelectorAll('#productLinkTabs button').forEach(btn => btn.onclick = () => { document.querySelectorAll('#productLinkTabs button').forEach(b => b.classList.remove('active')); btn.classList.add('active'); state.productLink = btn.dataset.link; state.productCategory = '全部'; renderProducts(); });
  const links = document.querySelectorAll('.nav a');
  links.forEach(a => a.onclick = () => { links.forEach(x => x.classList.remove('active')); a.classList.add('active'); });
  document.getElementById('modalClose').onclick = closeCreative;
  document.getElementById('creativeModal').onclick = e => { if (e.target.id === 'creativeModal') closeCreative(); };
  window.addEventListener('keydown', e => { if (e.key === 'Escape') closeCreative(); });
}
function renderAll() {
  renderDateControls(); renderTopbar(); renderOverviewCards(); renderFluctuation(); renderTreemaps(); renderProducts(); renderClientCards();
}
function init() { renderAll(); wireStaticEvents(); }
init();
</script>
</body>
</html>
'''


def main():
    data = build_data()
    html = HTML.replace("__PORTAL_DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    OUT_HTML.write_text(html, encoding="utf-8")
    print(OUT_HTML)


if __name__ == "__main__":
    main()
