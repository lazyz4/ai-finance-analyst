# -*- coding: utf-8 -*-
"""
分析引擎：不依赖 pandas，只用标准库 + SQLite。

职责边界：
  数据层：data/*.csv
  计算层：sql/schema.sql 里的视图（透视、比率、监测值、规则判定）
  本模块：把视图结果取出来，整理成前端要的 JSON

口径只在 SQL 里定义一次，命令行流水线（analysis/finance_analysis.py）、
Power BI（powerbi/measures.dax）和这个网页应用共用同一套视图，三边结果应当一致。
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from contextlib import closing
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
SQL_DIR = BASE / "sql"
DB_PATH = BASE / "outputs" / "finance.db"
UPLOAD_DIR = BASE / "app" / "data"
META_PATH = UPLOAD_DIR / "meta.json"

REQUIRED_ANNUAL_COLUMNS = ["period", "item", "value", "statement", "unit"]

# 季度科目与年度科目的对应关系（列示口径不同，需要显式映射）
QUARTER_TO_ANNUAL = {
    "营业收入": "营业总收入",
    "归母净利润": "净利润",
}


class DatasetError(ValueError):
    """上传的数据集不满足要求。"""


# --------------------------------------------------------------------------
# 数据集
# --------------------------------------------------------------------------
def active_dataset() -> dict:
    """返回当前生效的数据集信息。"""
    if META_PATH.exists():
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    return {
        "company": "美的集团股份有限公司（000333.SZ）",
        "source": "2025 年年度报告（巨潮资讯网，2026-03-31 披露）",
        "prior_label": "2024",
        "current_label": "2025",
        "currency": "人民币",
        "unit": "百万元",
    }


def _annual_csv() -> Path:
    meta = active_dataset()
    custom = UPLOAD_DIR / meta.get("annual_file", "")
    if meta.get("annual_file") and custom.exists():
        return custom
    return DATA_DIR / "financial_line_items.csv"


def _quarterly_csv() -> Path:
    meta = active_dataset()
    custom = UPLOAD_DIR / meta.get("quarterly_file", "")
    if meta.get("quarterly_file") and custom.exists():
        return custom
    return DATA_DIR / "quarterly_line_items.csv"


def _read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_database() -> None:
    """按 schema.sql 重建数据库，并装载当前数据集。"""
    annual = _read_rows(_annual_csv())
    quarterly = _read_rows(_quarterly_csv())
    rules = _read_rows(DATA_DIR / "indicator_rules.csv")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Windows 下文件被占用时无法删除，因此所有连接都必须显式关闭；
    # 注意 `with sqlite3.connect(...)` 只管理事务，不会关闭连接。
    DB_PATH.unlink(missing_ok=True)

    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        conn.executemany(
            "INSERT INTO financial_line_items (period, item, value, statement, unit) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    int(r["period"]),
                    r["item"].strip(),
                    float(r["value"]),
                    (r.get("statement") or "").strip() or "—",
                    (r.get("unit") or "").strip() or "百万元",
                )
                for r in annual
            ],
        )
        conn.executemany(
            "INSERT INTO quarterly_line_items (year, quarter, item, value, statement) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    int(r["year"]),
                    r["quarter"].strip(),
                    r["item"].strip(),
                    float(r["value"]),
                    (r.get("statement") or "").strip() or "分季度主要财务指标",
                )
                for r in quarterly
            ],
        )
        conn.executemany(
            "INSERT INTO indicator_rules "
            "(item, kind, monitor_basis, watch_threshold, alert_threshold, direction, rule_desc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    r["item"].strip(),
                    r["kind"].strip(),
                    r["monitor_basis"].strip(),
                    float(r["watch_threshold"]),
                    float(r["alert_threshold"]),
                    r["direction"].strip(),
                    r["rule_desc"].strip(),
                )
                for r in rules
            ],
        )
        conn.commit()


def ensure_database() -> None:
    if not DB_PATH.exists():
        build_database()


# --------------------------------------------------------------------------
# 数据集校验与替换
# --------------------------------------------------------------------------
def validate_annual_csv(text: str) -> tuple[list[dict], list[str]]:
    """校验上传的年度科目明细，返回 (记录, 期间标签)。"""
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in REQUIRED_ANNUAL_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise DatasetError(f"缺少必要列：{', '.join(missing)}。请先下载模板。")

    rows: list[dict] = []
    for i, row in enumerate(reader, start=2):
        try:
            period = int(str(row["period"]).strip())
            value = float(str(row["value"]).strip())
        except (TypeError, ValueError):
            raise DatasetError(f"第 {i} 行的 period 或 value 不是数字。")
        item = str(row["item"]).strip()
        if not item:
            raise DatasetError(f"第 {i} 行缺少科目名称 item。")
        rows.append(
            {
                "period": period,
                "item": item,
                "value": value,
                "statement": (row.get("statement") or "").strip() or "—",
                "unit": (row.get("unit") or "").strip() or "百万元",
            }
        )

    if not rows:
        raise DatasetError("文件里没有数据行。")

    periods = sorted({r["period"] for r in rows})
    if len(periods) != 2:
        raise DatasetError(
            f"需要正好两个对比期间，当前有 {len(periods)} 个：{periods}。同比与百分点变化依赖两个期间。"
        )

    by_period = {p: {r["item"] for r in rows if r["period"] == p} for p in periods}
    only_prior = by_period[periods[0]] - by_period[periods[1]]
    only_current = by_period[periods[1]] - by_period[periods[0]]
    if only_prior or only_current:
        raise DatasetError(
            "两个期间的科目不完全对应："
            f"仅前期有 {sorted(only_prior) or '无'}，仅当期有 {sorted(only_current) or '无'}。"
        )
    return rows, [str(p) for p in periods]


def replace_dataset(csv_text: str, company: str = "", source: str = "") -> dict:
    """用上传的数据集替换当前数据集，并重建数据库。"""
    rows, periods = validate_annual_csv(csv_text)

    # 视图里固定使用 2024 / 2025 两个期间列，这里把「前期→2024、当期→2025」做映射，
    # 原始年份标签保留在 meta 里用于界面显示。
    remap = {int(periods[0]): 2024, int(periods[1]): 2025}
    for r in rows:
        r["period"] = remap[r["period"]]

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = "financial_line_items_upload.csv"
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=["period", "item", "value", "statement", "unit"]
    )
    writer.writeheader()
    writer.writerows(rows)
    (UPLOAD_DIR / name).write_text(buffer.getvalue(), encoding="utf-8-sig")

    meta = active_dataset()
    meta.update(
        {
            "company": company.strip() or "上传数据集",
            "source": source.strip() or "用户上传",
            "prior_label": periods[0],
            "current_label": periods[1],
            "annual_file": name,
        }
    )
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    build_database()
    return meta


def reset_dataset() -> dict:
    if META_PATH.exists():
        META_PATH.unlink()
    build_database()
    return active_dataset()


# --------------------------------------------------------------------------
# 分析结果
# --------------------------------------------------------------------------
def _rows(conn: sqlite3.Connection, sql: str) -> list[dict]:
    cur = conn.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


KPI_SQL = """
SELECT rev_2024, rev_2025, cogs_2024, cogs_2025,
       op_2024, op_2025, ni_2024, ni_2025, ocf_2024, ocf_2025,
       ar_2024, ar_2025, inv_2024, inv_2025, ap_2024, ap_2025,
       cash_2024, cash_2025, ta_2024, ta_2025,
       gm_rate_2024, gm_rate_2025, ni_rate_2024, ni_rate_2025,
       ocf_rate_2024, ocf_rate_2025, three_exp_2024, three_exp_2025,
       cash_ratio_2024, cash_ratio_2025,
       dso_2024, dso_2025, dio_2024, dio_2025, dpo_2024, dpo_2025,
       ta_turn_2024, ta_turn_2025
FROM v_annual_ratios
"""

SIGNAL_SQL = """
SELECT item, kind, monitor_basis, direction, watch_threshold, alert_threshold,
       ROUND(monitor_value, 4) AS monitor_value, status, rule_desc
FROM v_signals
ORDER BY CASE status WHEN '预警' THEN 1 WHEN '关注' THEN 2 ELSE 3 END, item
"""

QUARTER_SQL = """
SELECT quarter, item, value
FROM quarterly_line_items
ORDER BY quarter, item
"""


def _pct(current: float, prior: float) -> float:
    return current / prior - 1 if prior else 0.0


def analysis() -> dict:
    ensure_database()
    meta = active_dataset()
    with closing(sqlite3.connect(DB_PATH)) as conn:
        kpi = _rows(conn, KPI_SQL)[0]
        signals = _rows(conn, SIGNAL_SQL)
        quarter_rows = _rows(conn, QUARTER_SQL)
        annual_items = _rows(
            conn,
            "SELECT period, item, value FROM financial_line_items ORDER BY period, item",
        )

    ccc = {
        y: kpi[f"dso_{y}"] + kpi[f"dio_{y}"] - kpi[f"dpo_{y}"] for y in ("2024", "2025")
    }
    unit = meta.get("unit", "百万元")
    kpis = [
        {
            "name": "营业总收入",
            "value": kpi["rev_2025"],
            "unit": unit,
            "yoy": _pct(kpi["rev_2025"], kpi["rev_2024"]),
        },
        {
            "name": "净利润",
            "value": kpi["ni_2025"],
            "unit": unit,
            "yoy": _pct(kpi["ni_2025"], kpi["ni_2024"]),
        },
        {
            "name": "经营活动现金流净额",
            "value": kpi["ocf_2025"],
            "unit": unit,
            "yoy": _pct(kpi["ocf_2025"], kpi["ocf_2024"]),
        },
        {
            "name": "现金含量",
            "value": kpi["cash_ratio_2025"],
            "unit": "倍",
            "change": kpi["cash_ratio_2025"] - kpi["cash_ratio_2024"],
        },
        {
            "name": "现金转换周期",
            "value": ccc["2025"],
            "unit": "天",
            "change": ccc["2025"] - ccc["2024"],
        },
    ]

    counts = {"预警": 0, "关注": 0, "正常": 0}
    for s in signals:
        counts[s["status"]] = counts.get(s["status"], 0) + 1

    quarters = sorted({r["quarter"] for r in quarter_rows})
    series: dict[str, dict] = {q: {"quarter": q} for q in quarters}
    for r in quarter_rows:
        series[r["quarter"]][r["item"]] = r["value"]

    return {
        "dataset": meta,
        "kpis": kpis,
        "signals": signals,
        "counts": counts,
        "total": len(signals),
        "quarterly": list(series.values()),
        "caveats": _caveats(annual_items, quarter_rows),
    }


def _caveats(annual_items: list[dict], quarter_rows: list[dict]) -> list[dict]:
    """季度合计与全年数勾稽。只在能对应上时给出，避免误报。"""
    annual_current = {
        r["item"]: r["value"] for r in annual_items if int(r["period"]) == 2025
    }
    sums: dict[str, float] = {}
    for r in quarter_rows:
        sums[r["item"]] = sums.get(r["item"], 0.0) + r["value"]

    out: list[dict] = []
    for q_item, q_sum in sums.items():
        target = QUARTER_TO_ANNUAL.get(q_item, q_item)
        annual = annual_current.get(target)
        if annual is None:
            continue
        diff = q_sum - annual
        out.append(
            {
                "quarter_item": q_item,
                "annual_item": target,
                "quarter_sum": round(q_sum, 3),
                "annual_value": round(annual, 3),
                "diff": round(diff, 3),
                "consistent": abs(diff) <= 0.01,
            }
        )
    out.sort(key=lambda d: abs(d["diff"]), reverse=True)
    return out


def build_llm_payload() -> dict:
    """给大模型的输入：只给信号、口径和阈值，不给结论。"""
    a = analysis()
    meta = a["dataset"]
    return {
        "company": meta.get("company"),
        "period": meta.get("current_label"),
        "unit": meta.get("unit"),
        "counts": a["counts"],
        "signals": [
            {
                "metric": s["item"],
                "kind": s["kind"],
                "basis": s["monitor_basis"],
                "value": s["monitor_value"],
                "direction": s["direction"],
                "watch_threshold": s["watch_threshold"],
                "alert_threshold": s["alert_threshold"],
                "status": s["status"],
                "rule": s["rule_desc"],
            }
            for s in a["signals"]
            if s["status"] != "正常"
        ],
        "data_caveats": [
            {
                "item": c["quarter_item"],
                "annual_item": c["annual_item"],
                "difference": c["diff"],
            }
            for c in a["caveats"]
        ],
    }
