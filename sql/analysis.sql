-- ============================================================
-- 财务经营分析｜查询集
-- 每个查询以 "-- @query: 名称" 开头，供 analysis/finance_analysis.py 逐条执行
-- ============================================================

-- @query: 年度主要指标与同比
SELECT '营业总收入' AS 指标, rev_2024 AS 金额_2024, rev_2025 AS 金额_2025,
       ROUND(rev_2025 / rev_2024 - 1, 4) AS 同比
FROM v_annual_pivot
UNION ALL SELECT '营业成本', cogs_2024, cogs_2025, ROUND(cogs_2025 / cogs_2024 - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '毛利额', rev_2024 - cogs_2024, rev_2025 - cogs_2025,
       ROUND((rev_2025 - cogs_2025) / (rev_2024 - cogs_2024) - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '营业利润', op_2024, op_2025, ROUND(op_2025 / op_2024 - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '净利润', ni_2024, ni_2025, ROUND(ni_2025 / ni_2024 - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '经营活动现金流净额', ocf_2024, ocf_2025, ROUND(ocf_2025 / ocf_2024 - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '应收账款', ar_2024, ar_2025, ROUND(ar_2025 / ar_2024 - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '存货', inv_2024, inv_2025, ROUND(inv_2025 / inv_2024 - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '应付账款', ap_2024, ap_2025, ROUND(ap_2025 / ap_2024 - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '货币资金', cash_2024, cash_2025, ROUND(cash_2025 / cash_2024 - 1, 4) FROM v_annual_pivot
UNION ALL SELECT '资产总计', ta_2024, ta_2025, ROUND(ta_2025 / ta_2024 - 1, 4) FROM v_annual_pivot;

-- @query: 盈利能力比率
SELECT '毛利率' AS 指标, ROUND(gm_rate_2024, 4) AS 比率_2024, ROUND(gm_rate_2025, 4) AS 比率_2025,
       ROUND((gm_rate_2025 - gm_rate_2024) * 100, 4) AS 变化_百分点
FROM v_annual_ratios
UNION ALL SELECT '销售费用率', ROUND(sell_rate_2024, 4), ROUND(sell_rate_2025, 4),
       ROUND((sell_rate_2025 - sell_rate_2024) * 100, 4) FROM v_annual_ratios
UNION ALL SELECT '管理费用率', ROUND(admin_rate_2024, 4), ROUND(admin_rate_2025, 4),
       ROUND((admin_rate_2025 - admin_rate_2024) * 100, 4) FROM v_annual_ratios
UNION ALL SELECT '研发费用率', ROUND(rd_rate_2024, 4), ROUND(rd_rate_2025, 4),
       ROUND((rd_rate_2025 - rd_rate_2024) * 100, 4) FROM v_annual_ratios
UNION ALL SELECT '净利率', ROUND(ni_rate_2024, 4), ROUND(ni_rate_2025, 4),
       ROUND((ni_rate_2025 - ni_rate_2024) * 100, 4) FROM v_annual_ratios
UNION ALL SELECT '经营现金流率', ROUND(ocf_rate_2024, 4), ROUND(ocf_rate_2025, 4),
       ROUND((ocf_rate_2025 - ocf_rate_2024) * 100, 4) FROM v_annual_ratios;

-- @query: 营运资本与现金质量
SELECT '现金含量（倍）' AS 指标, ROUND(cash_ratio_2024, 4) AS 值_2024, ROUND(cash_ratio_2025, 4) AS 值_2025,
       ROUND(cash_ratio_2025 - cash_ratio_2024, 4) AS 变化
FROM v_annual_ratios
UNION ALL SELECT '三费占收入比', ROUND(three_exp_2024, 4), ROUND(three_exp_2025, 4),
       ROUND((three_exp_2025 - three_exp_2024) * 100, 4) FROM v_annual_ratios
UNION ALL SELECT '应收账款周转天数', ROUND(dso_2024, 2), ROUND(dso_2025, 2),
       ROUND(dso_2025 - dso_2024, 2) FROM v_annual_ratios
UNION ALL SELECT '存货周转天数', ROUND(dio_2024, 2), ROUND(dio_2025, 2),
       ROUND(dio_2025 - dio_2024, 2) FROM v_annual_ratios
UNION ALL SELECT '应付账款周转天数', ROUND(dpo_2024, 2), ROUND(dpo_2025, 2),
       ROUND(dpo_2025 - dpo_2024, 2) FROM v_annual_ratios
UNION ALL SELECT '现金转换周期', ROUND(dso_2024 + dio_2024 - dpo_2024, 2),
       ROUND(dso_2025 + dio_2025 - dpo_2025, 2),
       ROUND((dso_2025 + dio_2025 - dpo_2025) - (dso_2024 + dio_2024 - dpo_2024), 2) FROM v_annual_ratios
UNION ALL SELECT '总资产周转率', ROUND(ta_turn_2024, 4), ROUND(ta_turn_2025, 4),
       ROUND(ta_turn_2025 - ta_turn_2024, 4) FROM v_annual_ratios;

-- @query: 异常信号汇总
SELECT status AS 状态, COUNT(*) AS 事项数
FROM v_signals
GROUP BY status
ORDER BY CASE status WHEN '预警' THEN 1 WHEN '关注' THEN 2 ELSE 3 END;

-- @query: 异常信号清单
SELECT item AS 指标, kind AS 类型, monitor_basis AS 监测口径,
       monitor_value AS 监测值, direction AS 方向,
       watch_threshold AS 关注阈值, alert_threshold AS 预警阈值,
       status AS 状态, rule_desc AS 触发规则
FROM v_signals
WHERE status <> '正常'
ORDER BY CASE status WHEN '预警' THEN 1 ELSE 2 END, item;

-- @query: 全部指标判定明细
SELECT item AS 指标, kind AS 类型, monitor_basis AS 监测口径,
       monitor_value AS 监测值, status AS 状态, rule_desc AS 触发规则
FROM v_signals
ORDER BY CASE status WHEN '预警' THEN 1 WHEN '关注' THEN 2 ELSE 3 END, item;

-- @query: 季度主要指标
SELECT quarter AS 季度,
       ROUND(SUM(CASE WHEN item = '营业收入'           THEN value END), 3) AS 营业收入,
       ROUND(SUM(CASE WHEN item = '归母净利润'         THEN value END), 3) AS 归母净利润,
       ROUND(SUM(CASE WHEN item = '扣非净利润'         THEN value END), 3) AS 扣非净利润,
       ROUND(SUM(CASE WHEN item = '经营活动现金流净额' THEN value END), 3) AS 经营活动现金流净额
FROM quarterly_line_items
WHERE year = 2025
GROUP BY quarter
ORDER BY quarter;

-- @query: 季度合计与全年数勾稽
SELECT q.item AS 项目,
       ROUND(SUM(q.value), 3) AS 季度合计,
       a.value                AS 全年数,
       ROUND(SUM(q.value) - a.value, 3) AS 差异,
       a.item                 AS 全年数口径
FROM quarterly_line_items q
JOIN financial_line_items a
  ON a.period = 2025
 AND (
      (q.item = '营业收入'           AND a.item = '营业总收入')
   OR (q.item = '归母净利润'         AND a.item = '净利润')
   OR (q.item = '经营活动现金流净额' AND a.item = '经营活动现金流净额')
 )
GROUP BY q.item, a.value, a.item
ORDER BY ABS(ROUND(SUM(q.value) - a.value, 3)) DESC;
