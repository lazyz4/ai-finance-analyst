// ============================================================================
// Power BI｜Power Query M 代码
//
// 用法：Power BI Desktop → 主页 → 转换数据 → 新建源 → 空白查询 →
//       高级编辑器 → 粘贴下面对应的一段 → 完成
//
// 每段开头的「路径」是 CSV 所在文件夹，改成你本机 powerbi\tables 的实际位置。
// 如果不想写 M 代码，可以直接导入同目录下已经算好的「年度透视.csv」，
// 两种方式得到的表结构完全相同，后面所有 DAX 度量值都能用。
// ============================================================================


// ---------------------------------------------------------------------------
// 查询 1：财务明细（长表，Power BI 自动生成的关系不需要，仅作查看与校验）
// ---------------------------------------------------------------------------
let
    路径 = "C:\Users\13155\Documents\Codex\2026-09-16\zh\outputs\ai-finance-analyst\powerbi\tables\",
    源 = Csv.Document(
        File.Contents(路径 & "财务明细.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    提升标题 = Table.PromoteHeaders(源, [PromoteAllScalars = true]),
    设定类型 = Table.TransformColumnTypes(
        提升标题,
        {
            { "period", Int64.Type },
            { "item", type text },
            { "col_key", type text },
            { "value", type number },
            { "statement", type text },
            { "unit", type text }
        }
    )
in
    设定类型


// ---------------------------------------------------------------------------
// 查询 2：年度透视（把长表按「标准列名_期间」透视成一行宽表）
// 这一步是 Power BI 建模的关键：透视完成后，DAX 里的列名与 SQL 视图完全一致
// ---------------------------------------------------------------------------
let
    路径 = "C:\Users\13155\Documents\Codex\2026-09-16\zh\outputs\ai-finance-analyst\powerbi\tables\",
    源 = Csv.Document(
        File.Contents(路径 & "财务明细.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    提升标题 = Table.PromoteHeaders(源, [PromoteAllScalars = true]),
    设定类型 = Table.TransformColumnTypes(
        提升标题,
        {
            { "period", Int64.Type },
            { "item", type text },
            { "col_key", type text },
            { "value", type number }
        }
    ),
    生成列名 = Table.AddColumn(
        设定类型,
        "列名",
        each [col_key] & "_" & Text.From([period]),
        type text
    ),
    只留两列 = Table.SelectColumns(生成列名, { "列名", "value" }),
    透视 = Table.Pivot(
        只留两列,
        List.Distinct(只留两列[列名]),
        "列名",
        "value",
        List.Sum
    ),
    结果 = Table.TransformColumnTypes(
        透视,
        List.Transform(Table.ColumnNames(透视), each { _, type number })
    )
in
    结果


// ---------------------------------------------------------------------------
// 查询 3：规则（22 条异常判定规则与阈值）
// ---------------------------------------------------------------------------
let
    路径 = "C:\Users\13155\Documents\Codex\2026-09-16\zh\outputs\ai-finance-analyst\powerbi\tables\",
    源 = Csv.Document(
        File.Contents(路径 & "规则.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    提升标题 = Table.PromoteHeaders(源, [PromoteAllScalars = true]),
    设定类型 = Table.TransformColumnTypes(
        提升标题,
        {
            { "item", type text },
            { "kind", type text },
            { "monitor_basis", type text },
            { "watch_threshold", type number },
            { "alert_threshold", type number },
            { "direction", type text },
            { "rule_desc", type text }
        }
    )
in
    设定类型


// ---------------------------------------------------------------------------
// 查询 4：指标监测（SQL 算出的监测值，用于与 DAX 对账）
// ---------------------------------------------------------------------------
let
    路径 = "C:\Users\13155\Documents\Codex\2026-09-16\zh\outputs\ai-finance-analyst\powerbi\tables\",
    源 = Csv.Document(
        File.Contents(路径 & "指标监测.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    提升标题 = Table.PromoteHeaders(源, [PromoteAllScalars = true]),
    设定类型 = Table.TransformColumnTypes(
        提升标题,
        {
            { "item", type text },
            { "kind", type text },
            { "monitor_basis", type text },
            { "sql_monitor_value", type number }
        }
    )
in
    设定类型


// ---------------------------------------------------------------------------
// 查询 5：指标状态（SQL 判定结果，用于核对 DAX 判定是否一致）
// ---------------------------------------------------------------------------
let
    路径 = "C:\Users\13155\Documents\Codex\2026-09-16\zh\outputs\ai-finance-analyst\powerbi\tables\",
    源 = Csv.Document(
        File.Contents(路径 & "指标状态.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    提升标题 = Table.PromoteHeaders(源, [PromoteAllScalars = true]),
    设定类型 = Table.TransformColumnTypes(
        提升标题,
        {
            { "item", type text },
            { "status", type text },
            { "rule_desc", type text }
        }
    )
in
    设定类型


// ---------------------------------------------------------------------------
// 查询 6：季度明细
// 页面上按季度展示时，把 item 放进「列」字段即可，不需要额外透视
// ---------------------------------------------------------------------------
let
    路径 = "C:\Users\13155\Documents\Codex\2026-09-16\zh\outputs\ai-finance-analyst\powerbi\tables\",
    源 = Csv.Document(
        File.Contents(路径 & "季度明细.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    提升标题 = Table.PromoteHeaders(源, [PromoteAllScalars = true]),
    设定类型 = Table.TransformColumnTypes(
        提升标题,
        {
            { "year", Int64.Type },
            { "quarter", type text },
            { "item", type text },
            { "value", type number },
            { "statement", type text }
        }
    )
in
    设定类型
