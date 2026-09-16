-- ============================================================
-- 财务经营分析｜数据模型（SQLite）
-- 口径：单位百万元，人民币；数据来自美的集团 2025 年年度报告
-- ============================================================

DROP VIEW  IF EXISTS v_signals;
DROP VIEW  IF EXISTS v_indicator_monitor;
DROP VIEW  IF EXISTS v_annual_ratios;
DROP VIEW  IF EXISTS v_annual_pivot;
DROP TABLE IF EXISTS indicator_rules;
DROP TABLE IF EXISTS quarterly_line_items;
DROP TABLE IF EXISTS financial_line_items;

-- ---------- 事实表：年度科目余额与损益项目 ----------
CREATE TABLE financial_line_items (
    period     INTEGER NOT NULL,          -- 报告期（年）
    item       TEXT    NOT NULL,          -- 科目／指标名称
    value      REAL    NOT NULL,          -- 金额，单位：百万元
    statement  TEXT    NOT NULL,          -- 所属报表
    unit       TEXT    NOT NULL DEFAULT '百万元',
    PRIMARY KEY (period, item)
);

-- ---------- 事实表：分季度主要财务指标 ----------
CREATE TABLE quarterly_line_items (
    year       INTEGER NOT NULL,
    quarter    TEXT    NOT NULL,          -- Q1 ~ Q4
    item       TEXT    NOT NULL,
    value      REAL    NOT NULL,
    statement  TEXT    NOT NULL,
    PRIMARY KEY (year, quarter, item)
);

-- ---------- 参数表：异常判定规则（阈值可调） ----------
CREATE TABLE indicator_rules (
    item            TEXT NOT NULL PRIMARY KEY,
    kind            TEXT NOT NULL,        -- 金额 / 比率 / 倍数 / 天数 / 次数
    monitor_basis   TEXT NOT NULL,        -- 监测值口径
    watch_threshold REAL NOT NULL,        -- 关注阈值
    alert_threshold REAL NOT NULL,        -- 预警阈值
    direction       TEXT NOT NULL CHECK (direction IN ('高于', '低于')),
    rule_desc       TEXT NOT NULL
);

-- ---------- 视图：年度数据透视（一行一期两列，便于同比计算） ----------
CREATE VIEW v_annual_pivot AS
SELECT
    MAX(CASE WHEN period = 2024 AND item = '营业总收入'         THEN value END) AS rev_2024,
    MAX(CASE WHEN period = 2025 AND item = '营业总收入'         THEN value END) AS rev_2025,
    MAX(CASE WHEN period = 2024 AND item = '营业成本'           THEN value END) AS cogs_2024,
    MAX(CASE WHEN period = 2025 AND item = '营业成本'           THEN value END) AS cogs_2025,
    MAX(CASE WHEN period = 2024 AND item = '销售费用'           THEN value END) AS sell_2024,
    MAX(CASE WHEN period = 2025 AND item = '销售费用'           THEN value END) AS sell_2025,
    MAX(CASE WHEN period = 2024 AND item = '管理费用'           THEN value END) AS admin_2024,
    MAX(CASE WHEN period = 2025 AND item = '管理费用'           THEN value END) AS admin_2025,
    MAX(CASE WHEN period = 2024 AND item = '研发费用'           THEN value END) AS rd_2024,
    MAX(CASE WHEN period = 2025 AND item = '研发费用'           THEN value END) AS rd_2025,
    MAX(CASE WHEN period = 2024 AND item = '营业利润'           THEN value END) AS op_2024,
    MAX(CASE WHEN period = 2025 AND item = '营业利润'           THEN value END) AS op_2025,
    MAX(CASE WHEN period = 2024 AND item = '净利润'             THEN value END) AS ni_2024,
    MAX(CASE WHEN period = 2025 AND item = '净利润'             THEN value END) AS ni_2025,
    MAX(CASE WHEN period = 2024 AND item = '经营活动现金流净额' THEN value END) AS ocf_2024,
    MAX(CASE WHEN period = 2025 AND item = '经营活动现金流净额' THEN value END) AS ocf_2025,
    MAX(CASE WHEN period = 2024 AND item = '应收账款'           THEN value END) AS ar_2024,
    MAX(CASE WHEN period = 2025 AND item = '应收账款'           THEN value END) AS ar_2025,
    MAX(CASE WHEN period = 2024 AND item = '存货'               THEN value END) AS inv_2024,
    MAX(CASE WHEN period = 2025 AND item = '存货'               THEN value END) AS inv_2025,
    MAX(CASE WHEN period = 2024 AND item = '应付账款'           THEN value END) AS ap_2024,
    MAX(CASE WHEN period = 2025 AND item = '应付账款'           THEN value END) AS ap_2025,
    MAX(CASE WHEN period = 2024 AND item = '货币资金'           THEN value END) AS cash_2024,
    MAX(CASE WHEN period = 2025 AND item = '货币资金'           THEN value END) AS cash_2025,
    MAX(CASE WHEN period = 2024 AND item = '资产总计'           THEN value END) AS ta_2024,
    MAX(CASE WHEN period = 2025 AND item = '资产总计'           THEN value END) AS ta_2025
FROM financial_line_items;

-- ---------- 视图：年度水平值与比率（比率保留小数，转百分点在下一层处理） ----------
CREATE VIEW v_annual_ratios AS
SELECT
    p.*,
    (p.rev_2024 - p.cogs_2024) / p.rev_2024                     AS gm_rate_2024,
    (p.rev_2025 - p.cogs_2025) / p.rev_2025                     AS gm_rate_2025,
    p.sell_2024  / p.rev_2024                                   AS sell_rate_2024,
    p.sell_2025  / p.rev_2025                                   AS sell_rate_2025,
    p.admin_2024 / p.rev_2024                                   AS admin_rate_2024,
    p.admin_2025 / p.rev_2025                                   AS admin_rate_2025,
    p.rd_2024    / p.rev_2024                                   AS rd_rate_2024,
    p.rd_2025    / p.rev_2025                                   AS rd_rate_2025,
    p.ni_2024    / p.rev_2024                                   AS ni_rate_2024,
    p.ni_2025    / p.rev_2025                                   AS ni_rate_2025,
    p.ocf_2024   / p.rev_2024                                   AS ocf_rate_2024,
    p.ocf_2025   / p.rev_2025                                   AS ocf_rate_2025,
    p.ar_2024    / p.rev_2024                                   AS ar_rev_2024,
    p.ar_2025    / p.rev_2025                                   AS ar_rev_2025,
    (p.sell_2024 + p.admin_2024 + p.rd_2024) / p.rev_2024        AS three_exp_2024,
    (p.sell_2025 + p.admin_2025 + p.rd_2025) / p.rev_2025        AS three_exp_2025,
    p.ocf_2024   / p.ni_2024                                    AS cash_ratio_2024,
    p.ocf_2025   / p.ni_2025                                    AS cash_ratio_2025,
    p.ar_2024    / p.rev_2024  * 365                            AS dso_2024,
    p.ar_2025    / p.rev_2025  * 365                            AS dso_2025,
    p.inv_2024   / p.cogs_2024 * 365                            AS dio_2024,
    p.inv_2025   / p.cogs_2025 * 365                            AS dio_2025,
    p.ap_2024    / p.cogs_2024 * 365                            AS dpo_2024,
    p.ap_2025    / p.cogs_2025 * 365                            AS dpo_2025,
    p.rev_2024   / p.ta_2024                                    AS ta_turn_2024,
    p.rev_2025   / p.ta_2025                                    AS ta_turn_2025
FROM v_annual_pivot p;

-- ---------- 视图：监测值（与规则阈值同口径） ----------
CREATE VIEW v_indicator_monitor AS
WITH r AS (
    SELECT
        *,
        dso_2024 + dio_2024 - dpo_2024 AS ccc_2024,
        dso_2025 + dio_2025 - dpo_2025 AS ccc_2025
    FROM v_annual_ratios
)
SELECT '营业总收入'             AS item, '金额' AS kind, '%（同比变化率）'  AS monitor_basis, (rev_2025 / rev_2024 - 1) * 100            AS monitor_value FROM r
UNION ALL SELECT '营业成本',            '金额', '%（同比变化率）',       (cogs_2025 / cogs_2024 - 1) * 100                       FROM r
UNION ALL SELECT '毛利额',              '金额', '%（同比变化率）',       (((rev_2025 - cogs_2025) / (rev_2024 - cogs_2024)) - 1) * 100 FROM r
UNION ALL SELECT '毛利率',              '比率', 'pp（百分点变化）',      (gm_rate_2025 - gm_rate_2024) * 100                      FROM r
UNION ALL SELECT '销售费用率',          '比率', 'pp（百分点变化）',      (sell_rate_2025 - sell_rate_2024) * 100                  FROM r
UNION ALL SELECT '管理费用率',          '比率', 'pp（百分点变化）',      (admin_rate_2025 - admin_rate_2024) * 100                FROM r
UNION ALL SELECT '研发费用率',          '比率', 'pp（百分点变化）',      (rd_rate_2025 - rd_rate_2024) * 100                      FROM r
UNION ALL SELECT '营业利润',            '金额', '%（同比变化率）',       (op_2025 / op_2024 - 1) * 100                            FROM r
UNION ALL SELECT '净利率',              '比率', 'pp（百分点变化）',      (ni_rate_2025 - ni_rate_2024) * 100                      FROM r
UNION ALL SELECT '经营现金流率',        '比率', 'pp（百分点变化）',      (ocf_rate_2025 - ocf_rate_2024) * 100                    FROM r
UNION ALL SELECT '应收账款',            '金额', '%（同比变化率）',       (ar_2025 / ar_2024 - 1) * 100                            FROM r
UNION ALL SELECT '应收账款/收入',       '比率', 'pp（百分点变化）',      (ar_rev_2025 - ar_rev_2024) * 100                        FROM r
UNION ALL SELECT '存货',                '金额', '%（同比变化率）',       (inv_2025 / inv_2024 - 1) * 100                          FROM r
UNION ALL SELECT '应付账款',            '金额', '%（同比变化率）',       (ap_2025 / ap_2024 - 1) * 100                            FROM r
UNION ALL SELECT '货币资金',            '金额', '%（同比变化率）',       (cash_2025 / cash_2024 - 1) * 100                        FROM r
UNION ALL SELECT '现金含量',            '倍数', '倍（同比变化）',         cash_ratio_2025 - cash_ratio_2024                        FROM r
UNION ALL SELECT '三费占收入比',        '比率', 'pp（百分点变化）',      (three_exp_2025 - three_exp_2024) * 100                  FROM r
UNION ALL SELECT '应收账款周转天数',    '天数', '天（同比变化）',         dso_2025 - dso_2024                                      FROM r
UNION ALL SELECT '存货周转天数',        '天数', '天（同比变化）',         dio_2025 - dio_2024                                      FROM r
UNION ALL SELECT '应付账款周转天数',    '天数', '天（同比变化）',         dpo_2025 - dpo_2024                                      FROM r
UNION ALL SELECT '现金转换周期',        '天数', '天（同比变化）',         ccc_2025 - ccc_2024                                      FROM r
UNION ALL SELECT '总资产周转率',        '次数', '次（同比变化）',         ta_turn_2025 - ta_turn_2024                              FROM r;

-- ---------- 视图：规则命中结果 ----------
CREATE VIEW v_signals AS
SELECT
    m.item,
    r.kind,
    m.monitor_basis,
    r.direction,
    r.watch_threshold,
    r.alert_threshold,
    ROUND(m.monitor_value, 4) AS monitor_value,
    CASE
        WHEN r.direction = '高于' THEN
            CASE WHEN m.monitor_value >= r.alert_threshold THEN '预警'
                 WHEN m.monitor_value >= r.watch_threshold THEN '关注'
                 ELSE '正常' END
        ELSE
            CASE WHEN m.monitor_value <= r.alert_threshold THEN '预警'
                 WHEN m.monitor_value <= r.watch_threshold THEN '关注'
                 ELSE '正常' END
    END AS status,
    r.rule_desc
FROM v_indicator_monitor m
JOIN indicator_rules r ON r.item = m.item;
