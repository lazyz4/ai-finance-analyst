# AI 财务经营分析助手

用公开披露的真实上市公司数据，把「数据 → 指标 → 规则识别异常 → AI 解读」这条链路做成可运行、可复算、可追溯的一套东西。

数据对象：美的集团股份有限公司（000333.SZ）2025 年年度报告，单位百万元，人民币。

## 为什么不是一张 Excel 表

一张手填的 Excel 只能证明会把数字汇总。招聘里真正想看的是这条链路能不能跑起来、口径是否说得清、结论能不能追到原始报表。所以这套东西分了五层，每层单独可查：

| 层 | 位置 | 解决的问题 |
| --- | --- | --- |
| 数据层 | `data/*.csv` | 科目余额与季度指标按「期间 × 科目」结构化存放，来源与所属报表写在表里 |
| 计算层 | `sql/schema.sql` | 建表、透视、比率、监测值、规则引擎全部是 SQL 视图，阈值可改 |
| 分析层 | `sql/analysis.sql`、`analysis/finance_analysis.py` | 同比、盈利比率、营运资本、规则命中、季度勾稽，一键输出报告与结构化信号 |
| 可视化层 | `powerbi/` | Power BI 数据模型、DAX 度量值与四页看板，用 DAX 把规则判定重算一遍与 SQL 对账 |
| 应用层 | `app/` | 在线工具：上传数据集、看信号、调用大模型生成可能原因与待核查事项、导出报告 |

`docs/AI财务经营分析助手_v2.xlsx` 是同一套逻辑的 Excel 版本。四套实现（Excel、SQL、DAX、网页应用）共用同一套口径与阈值，判定结果应当一致。

## 目录

```text
ai-finance-analyst/
├── data/
│   ├── financial_line_items.csv     # 年度科目余额与损益项目（13 项 × 2 期）
│   ├── quarterly_line_items.csv     # 2025 年分季度主要财务指标（4 项 × 4 季）
│   └── indicator_rules.csv          # 22 条异常判定规则与阈值
├── sql/
│   ├── schema.sql                   # 表、视图、规则引擎
│   └── analysis.sql                 # 查询集（-- @query: 名称 切分）
├── analysis/
│   ├── finance_analysis.py          # 流水线：CSV → SQLite → 报告 + 结构化信号
│   ├── export_for_powerbi.py        # 导出 Power BI 所需的 6 张表
│   └── requirements.txt
├── powerbi/
│   ├── README.md                    # 从安装到四个页面的完整步骤
│   ├── queries.m                    # Power Query M 代码
│   ├── measures.dax                 # 度量值（含规则引擎与对账）
│   ├── layout.svg                   # 四页看板布局线框
│   └── tables/                      # 导出的 CSV（由 export_for_powerbi.py 生成）
├── app/
│   ├── engine.py                    # 分析引擎（只用标准库 + SQLite）
│   ├── llm.py                        # 大模型客户端（BYOK，只做解释不做判定）
│   ├── main.py                      # FastAPI 接口与报告导出
│   ├── static/index.html            # 前端单页
│   ├── requirements.txt
│   └── start.bat                    # Windows 双击启动
└── docs/
    └── AI财务经营分析助手_v2.xlsx     # 同口径的 Excel 底稿
```

## 快速开始（命令行流水线）

```bash
pip install -r analysis/requirements.txt
python analysis/finance_analysis.py
```

输出写在 `outputs/`：

- `report.md`：分析报告，含结论摘要、各维度指标表与勾稽核对
- `signals.json`：结构化信号，字段与 Prompt 里的 JSON 结构一致
- `signals.csv`：触发规则的事项清单
- `finance.db`：SQLite 数据库，可直接用任意 SQL 客户端打开复核

也可以只跑 SQL：

```bash
sqlite3 outputs/finance.db < sql/schema.sql
sqlite3 outputs/finance.db "SELECT * FROM v_signals WHERE status <> '正常';"
```

## 快速开始（在线应用）

```bash
pip install -r app/requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 <http://127.0.0.1:8000>。Windows 也可以直接双击 `app/start.bat`。

页面能做四件事：

1. 展示核心指标、22 项指标判定明细、分季度趋势与口径核对；
2. 用你自己的 API Key 调用大模型，把规则命中的信号翻译成「可能原因 + 待核查事项」；
3. 上传两个期间的科目明细，换成别的公司重新分析；
4. 导出 Markdown 分析报告。

支持的模型服务商：DeepSeek、OpenAI、Kimi、硅基流动、智谱、本地 Ollama，以及任意 OpenAI 兼容接口。API Key 只保存在浏览器本地，服务端只做转发，不存储、不写日志。

## 快速开始（Power BI）

```bash
python analysis/export_for_powerbi.py
```

然后按 `powerbi/README.md` 操作，从安装 Power BI Desktop 到四个页面逐页都有了。看板设计稿见 `powerbi/layout.svg`，用浏览器直接打开即可。

## 部署上线

项目自带 `Dockerfile` 与 `railway.json`，可以直接部署成一个公开网址。

**Railway（推荐，流程与你的复习整合包一致）**

1. 把项目推到 GitHub；
2. 打开 <https://railway.app/new>，选 Deploy from GitHub repo，选中该仓库；
3. Railway 会自动识别 `Dockerfile` 完成构建；
4. 在 Settings → Networking 里生成公网域名，打开即可访问。

不需要配置任何环境变量：模型 Key 由访问者在页面上自己填，服务端不保存。

**本地 Docker**

```bash
docker build -t ai-finance-analyst .
docker run -p 8000:8000 ai-finance-analyst
```

说明：容器文件系统是临时的，重启后上传的数据集会回到内置的美的集团数据集，`outputs/finance.db` 会在启动时按需重建。作为演示环境这正好是想要的行为。

## 规则引擎

判定不靠人工判断，靠一张可编辑的阈值表。每条规则包含指标、类型、监测口径、关注阈值、预警阈值、方向和规则说明。

监测值按类型换算成同一口径，再和阈值比较：

| 类型 | 监测值口径 | 例 |
| --- | --- | --- |
| 金额 | 同比变化率（%） | 货币资金 -39.29% ≤ -30%，命中关注 |
| 比率 | 百分点变化（pp） | 经营现金流率 -3.16pp ≤ -2pp，命中关注 |
| 倍数 | 同比变化（倍） | 现金含量 -0.36 倍 ≤ -0.3 倍，命中关注 |
| 天数 | 同比变化（天） | 存货周转天数 -6.96 天，高于方向未命中 |
| 次数 | 同比变化（次） | 总资产周转率 +0.08 次，低于方向未命中 |

改一个阈值，`v_signals`、报告和 Excel 里的状态会同时变。当前数据下的结果是：预警 0 项、关注 3 项、正常 19 项。

## 2025 年主要发现

- 营业总收入同比增长 12.08%、净利润同比增长 14.87%，但经营活动现金流净额同比下降 11.84%，盈利与现金创造方向不一致。
- 现金含量（经营现金流净额 ÷ 净利润）从 1.56 倍降到 1.20 倍；同时现金转换周期从 -3.95 天改善到 -10.22 天。营运资本效率改善而经营现金流下降，说明现金流出变化可能来自营运资本以外的项目。
- 第四季度经营活动现金流净额为 -3,720.155 百万元，归母净利润 6,062.028 百万元，明显低于前三季度。
- 货币资金同比下降 39.29%，属于关注事项。

## 数据口径与限制

- 数据全部来自公开披露的年度报告，不使用虚构数据，来源链接见 Excel 的「来源与证据」工作表。
- 周转天数按期末余额计算，未使用期初期末平均余额，与其他口径的周转天数不可直接比较。
- 应收账款为资产负债表「应收账款」项目，不含应收票据与应收款项融资。
- 季度指标合计与全年数存在两处差异：营业收入相差 2,050.676 百万元（营业总收入 与 营业收入 的列示口径），归母净利润相差 574.785 百万元（是否含少数股东损益）。季度经营活动现金流净额合计与全年数完全一致。
- 本项目的输出定位是辅助分析，不构成结论、投资建议或对公司经营状况的判断依据。

## 还没做的部分

- 报表页码级的引用标注（当前定位到报表名称，未到页码）。
- 年报 PDF / Excel 的自动抽取。现在上传需要按模板整理好的 CSV；不同公司年报版式差异大，自动抽取准确率无法保证，宁可先不做。
- 多期（三年以上）趋势与同业对比。
- 规则库按行业分组。当前 22 条规则是通用阈值，制造业与互联网的合理区间不同。
- 把 AI 解读结果写回报告并保留引用来源，形成「数字 → 规则 → 解释 → 核查记录」的完整闭环。
