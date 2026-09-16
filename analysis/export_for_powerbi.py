#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把 SQL 层的结果导出成 Power BI 可直接导入的 CSV。

分层思路：SQL 负责口径、透视与监测值；Power BI 负责建模、DAX 度量值与可视化。
导出的「年度透视」列名与 sql/schema.sql 中 v_annual_pivot 的列名保持一致，
因此 DAX 里引用的列名与 SQL 里看到的完全相同，便于两边对账。

用法：
    python analysis/export_for_powerbi.py
"""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from finance_analysis import build_database, read_source_frames  # noqa: E402

DB = BASE / "outputs" / "finance.db"
OUT = BASE / "powerbi" / "tables"

EXPORTS = {
    "财务明细": """
        SELECT period, item,
               CASE item
                   WHEN '营业总收入'         THEN 'rev'
                   WHEN '营业成本'           THEN 'cogs'
                   WHEN '销售费用'           THEN 'sell'
                   WHEN '管理费用'           THEN 'admin'
                   WHEN '研发费用'           THEN 'rd'
                   WHEN '营业利润'           THEN 'op'
                   WHEN '净利润'             THEN 'ni'
                   WHEN '经营活动现金流净额' THEN 'ocf'
                   WHEN '应收账款'           THEN 'ar'
                   WHEN '存货'               THEN 'inv'
                   WHEN '应付账款'           THEN 'ap'
                   WHEN '货币资金'           THEN 'cash'
                   WHEN '资产总计'           THEN 'ta'
               END AS col_key,
               value, statement, unit
        FROM financial_line_items
        ORDER BY period, item
    """,
    "季度明细": "SELECT year, quarter, item, value, statement FROM quarterly_line_items ORDER BY quarter, item",
    "规则": (
        "SELECT item, kind, monitor_basis, watch_threshold, alert_threshold, direction, rule_desc "
        "FROM indicator_rules ORDER BY rowid"
    ),
    "年度透视": "SELECT * FROM v_annual_pivot",
    # 把规则字段一并拍平：这样 Power BI 里不需要建任何关系，
    # 矩阵按「指标」逐行取值时 SELECTEDVALUE 就能拿到方向与阈值。
    "指标监测": """
        SELECT item, kind, monitor_basis, direction,
               watch_threshold, alert_threshold, rule_desc,
               ROUND(monitor_value, 4) AS sql_monitor_value,
               status AS sql_status
        FROM v_signals
        ORDER BY CASE status WHEN '预警' THEN 1 WHEN '关注' THEN 2 ELSE 3 END, item
    """,
    "指标状态": (
        "SELECT item, status, rule_desc FROM v_signals "
        "ORDER BY CASE status WHEN '预警' THEN 1 WHEN '关注' THEN 2 ELSE 3 END, item"
    ),
}


def main() -> int:
    if not DB.exists():
        print(f"未找到 {DB}，先按 schema 重建数据库")
        build_database(DB, read_source_frames())

    OUT.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB)) as conn:
        for name, sql in EXPORTS.items():
            df = pd.read_sql_query(sql, conn)
            path = OUT / f"{name}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"{name:8s} {len(df):3d} 行  ->  {path.relative_to(BASE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
