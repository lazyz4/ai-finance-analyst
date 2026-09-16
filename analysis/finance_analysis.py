#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
财务经营分析流水线
------------------
数据层：data/*.csv（来自公开披露的年度报告）
计算层：sql/schema.sql（建表、视图、规则引擎）
分析层：sql/analysis.sql（逐条查询）
输出层：outputs/report.md（分析报告）、outputs/signals.json（供 AI 层调用的结构化信号）

用法：
    python analysis/finance_analysis.py
    python analysis/finance_analysis.py --outdir outputs
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
SQL_DIR = BASE / "sql"

TABLES = {
    "financial_line_items": ["period", "item", "value", "statement", "unit"],
    "quarterly_line_items": ["year", "quarter", "item", "value", "statement"],
    "indicator_rules": [
        "item",
        "kind",
        "monitor_basis",
        "watch_threshold",
        "alert_threshold",
        "direction",
        "rule_desc",
    ],
}

ORDER = ["预警", "关注", "正常"]


def read_source_frames() -> dict[str, pd.DataFrame]:
    """读取 CSV 数据层。"""
    frames: dict[str, pd.DataFrame] = {}
    for table, columns in TABLES.items():
        path = DATA_DIR / f"{table}.csv"
        df = pd.read_csv(path, dtype={"item": str, "quarter": str})
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise ValueError(f"{path.name} 缺少列：{missing}")
        frames[table] = df[columns]
    return frames


def build_database(db_path: Path, frames: dict[str, pd.DataFrame]) -> None:
    """按 schema.sql 建库，并把 CSV 装载进事实表与参数表。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # 显式关闭连接：Windows 下被占用的数据库文件无法删除
    db_path.unlink(missing_ok=True)
    schema = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    with closing(sqlite3.connect(db_path)) as conn:
        conn.executescript(schema)
        for table, df in frames.items():
            placeholders = ", ".join("?" * len(df.columns))
            conn.executemany(
                f"INSERT INTO {table} VALUES ({placeholders})",
                df.itertuples(index=False, name=None),
            )
        conn.commit()


def load_queries(path: Path) -> list[tuple[str, str]]:
    """把 analysis.sql 按 `-- @query: 名称` 切成若干条查询。"""
    queries: list[tuple[str, str]] = []
    name: str | None = None
    buffer: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("-- @query:"):
            if name and buffer:
                queries.append((name, "\n".join(buffer).strip()))
            name = stripped.split(":", 1)[1].strip()
            buffer = []
        elif name is not None:
            buffer.append(line)
    if name and buffer:
        queries.append((name, "\n".join(buffer).strip()))
    return [(n, q.rstrip(";").strip() + ";") for n, q in queries if q.strip()]


def run_queries(db_path: Path) -> dict[str, pd.DataFrame]:
    """执行查询集，返回“查询名称 → 结果表”。"""
    results: dict[str, pd.DataFrame] = {}
    with closing(sqlite3.connect(db_path)) as conn:
        for name, sql in load_queries(SQL_DIR / "analysis.sql"):
            cur = conn.execute(sql)
            rows = cur.fetchall()
            results[name] = pd.DataFrame(rows, columns=[d[0] for d in cur.description])
    return results


def format_value(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".")
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "_（无记录）_\n"
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    divider = "| " + " | ".join("---" for _ in df.columns) + " |"
    lines = [header, divider]
    for row in df.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(format_value(v) for v in row) + " |")
    return "\n".join(lines) + "\n"


def build_signals(results: dict[str, pd.DataFrame]) -> dict:
    """把判定结果整理成结构化信号，供 AI 层直接消费。"""
    detail = results["全部指标判定明细"]
    summary = results["异常信号汇总"]
    quarterly = results["季度合计与全年数勾稽"]

    counts = {row["状态"]: int(row["事项数"]) for _, row in summary.iterrows()}
    signals = []
    for _, row in detail[detail["状态"] != "正常"].iterrows():
        signals.append(
            {
                "metric": row["指标"],
                "status": row["状态"],
                "basis": row["监测口径"],
                "value": round(float(row["监测值"]), 4),
                "rule": row["触发规则"],
                "possible_causes": [],
                "to_verify": [],
            }
        )

    caveats = []
    for _, row in quarterly.iterrows():
        if abs(float(row["差异"])) > 0.01:
            caveats.append(
                f"季度「{row['项目']}」合计 {row['季度合计']:,.3f} "
                f"与全年「{row['全年数口径']}」{row['全年数']:,.3f} "
                f"相差 {row['差异']:,.3f}，需先核对列示口径。"
            )

    return {
        "summary": (
            f"2025 年共判定 {int(summary['事项数'].sum())} 项指标："
            f"预警 {counts.get('预警', 0)} 项、关注 {counts.get('关注', 0)} 项、"
            f"正常 {counts.get('正常', 0)} 项。"
        ),
        "signals": signals,
        "data_caveats": caveats,
        "next_actions": [
            "对预警与关注事项逐项回到报表、附注与业务资料核查。",
            "统一季度与年度的收入、利润口径后再做结构与同比分析。",
        ],
    }


def build_report(results: dict[str, pd.DataFrame], signals: dict) -> str:
    sections = [
        "# 美的集团 2025 年财务经营分析报告",
        "",
        "数据来源：美的集团股份有限公司 2025 年年度报告（巨潮资讯网，2026-03-31 披露）。",
        "单位：百万元；比率类为百分数，变化量单位为百分点（pp）。",
        "",
        "## 结论摘要",
        "",
        signals["summary"],
        "",
    ]
    if signals["signals"]:
        sections.append("触发规则的事项：")
        sections.append("")
        for s in signals["signals"]:
            sections.append(f"- **{s['metric']}**（{s['status']}）：{s['value']:,.4f} {s['basis']}，{s['rule']}")
        sections.append("")
    if signals["data_caveats"]:
        sections.append("口径提示：")
        sections.append("")
        for c in signals["data_caveats"]:
            sections.append(f"- {c}")
        sections.append("")

    for name, df in results.items():
        sections.extend([f"## {name}", "", to_markdown(df), ""])
    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description="财务经营分析流水线")
    parser.add_argument("--outdir", default=str(BASE / "outputs"), help="输出目录")
    parser.add_argument("--db", default=str(BASE / "outputs" / "finance.db"), help="SQLite 数据库路径")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    frames = read_source_frames()
    build_database(Path(args.db), frames)
    results = run_queries(Path(args.db))
    signals = build_signals(results)
    report = build_report(results, signals)

    (outdir / "report.md").write_text(report, encoding="utf-8")
    (outdir / "signals.json").write_text(
        json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    results["异常信号清单"].to_csv(outdir / "signals.csv", index=False, encoding="utf-8-sig")

    print(signals["summary"])
    for s in signals["signals"]:
        print(f"  [{s['status']}] {s['metric']}: {s['value']:,.4f} {s['basis']}")
    print(f"\n报告已写入：{outdir / 'report.md'}")
    print(f"结构化信号：{outdir / 'signals.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
