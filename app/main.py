# -*- coding: utf-8 -*-
"""
AI 财务经营分析助手｜在线应用

本地运行：
    pip install -r app/requirements.txt
    python -m uvicorn app.main:app --reload --port 8000
浏览器打开 http://127.0.0.1:8000

接口：
    GET  /api/health            服务与数据集状态
    GET  /api/analysis          指标、信号、季度趋势、勾稽核对
    POST /api/explain           调用大模型生成可能原因与待核查事项（BYOK）
    POST /api/dataset           用上传的 CSV 替换数据集
    POST /api/dataset/reset     恢复内置数据集
    GET  /api/template          下载数据集模板
    GET  /api/report            下载 Markdown 分析报告
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# 保证无论用 `uvicorn app.main:app` 还是 `--app-dir app` 启动都能找到同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine
import llm

BASE = engine.BASE
STATIC_DIR = BASE / "app" / "static"

app = FastAPI(title="AI 财务经营分析助手", version="0.1.0")


class ExplainRequest(BaseModel):
    provider: str = "deepseek"
    apiKey: str = ""
    model: str = ""
    baseUrl: str = ""


class DatasetRequest(BaseModel):
    csv: str = Field(..., description="CSV 文本内容")
    company: str = ""
    source: str = ""


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "dataset": engine.active_dataset(),
        "providers": {
            k: {"label": v["label"], "model": v["model"], "needs_key": v["needs_key"]}
            for k, v in llm.PROVIDERS.items()
        },
        "note": "API Key 只保存在浏览器本地，服务端不存储、不写日志。",
    }


@app.get("/api/analysis")
def get_analysis() -> dict:
    return engine.analysis()


@app.post("/api/explain")
def post_explain(req: ExplainRequest) -> dict:
    payload = engine.build_llm_payload()
    try:
        return llm.explain(
            payload,
            provider=req.provider,
            api_key=req.apiKey.strip(),
            model=req.model.strip(),
            base_url=req.baseUrl.strip(),
        )
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/api/dataset")
def post_dataset(req: DatasetRequest) -> dict:
    try:
        meta = engine.replace_dataset(req.csv, req.company, req.source)
    except engine.DatasetError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"dataset": meta, "analysis": engine.analysis()}


@app.post("/api/dataset/reset")
def post_dataset_reset() -> dict:
    meta = engine.reset_dataset()
    return {"dataset": meta, "analysis": engine.analysis()}


@app.get("/api/template", response_class=PlainTextResponse)
def get_template() -> Response:
    rows = [
        "period,item,value,statement,unit",
        "2024,营业总收入,409084.266,合并利润表,百万元",
        "2025,营业总收入,458502.407,合并利润表,百万元",
        "2024,营业成本,299584.935,合并利润表,百万元",
        "2025,营业成本,335989.528,合并利润表,百万元",
        "# 说明：两个期间、同一套科目；item 名称需与规则表一致（共 22 项指标对应的 13 个科目）",
    ]
    return PlainTextResponse(
        "\n".join(rows) + "\n",
        headers={"Content-Disposition": 'attachment; filename="dataset_template.csv"'},
    )


def _markdown_report(data: dict) -> str:
    meta = data["dataset"]
    lines = [
        f"# {meta.get('company', '')} {meta.get('current_label', '')} 财务经营分析报告",
        "",
        f"数据来源：{meta.get('source', '')}",
        f"单位：{meta.get('unit', '百万元')}；比率类为百分数，变化量单位为百分点（pp）。",
        "",
        "## 结论摘要",
        "",
        f"本次共判定 {data['total']} 项指标："
        f"预警 {data['counts'].get('预警', 0)} 项、"
        f"关注 {data['counts'].get('关注', 0)} 项、"
        f"正常 {data['counts'].get('正常', 0)} 项。",
        "",
    ]

    flagged = [s for s in data["signals"] if s["status"] != "正常"]
    if flagged:
        lines += ["触发规则的事项：", ""]
        for s in flagged:
            lines.append(
                f"- **{s['item']}**（{s['status']}）：监测值 {s['monitor_value']} "
                f"{s['monitor_basis']}，{s['rule_desc']}"
            )
        lines.append("")

    caveats = [c for c in data["caveats"] if not c["consistent"]]
    if caveats:
        lines += ["口径提示（季度合计与全年数不一致）：", ""]
        for c in caveats:
            lines.append(
                f"- 季度「{c['quarter_item']}」合计 {c['quarter_sum']:,.3f}，"
                f"全年「{c['annual_item']}」{c['annual_value']:,.3f}，"
                f"相差 {c['diff']:,.3f}"
            )
        lines.append("")

    lines += ["## 核心指标", "", "| 指标 | 当期 | 同比／变化 |", "| --- | --- | --- |"]
    for k in data["kpis"]:
        if "yoy" in k:
            delta = f"{k['yoy'] * 100:+.2f}%"
        else:
            delta = f"{k['change']:+.2f} {k['unit']}"
        lines.append(f"| {k['name']} | {k['value']:,.4f} {k['unit']} | {delta} |")
    lines.append("")

    lines += [
        "## 全部指标判定明细",
        "",
        "| 指标 | 类型 | 监测口径 | 监测值 | 状态 | 触发规则 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in data["signals"]:
        rule = s["rule_desc"] if s["status"] != "正常" else "—"
        lines.append(
            f"| {s['item']} | {s['kind']} | {s['monitor_basis']} | "
            f"{s['monitor_value']} | {s['status']} | {rule} |"
        )
    lines.append("")

    if data["quarterly"]:
        items = [k for k in data["quarterly"][0] if k != "quarter"]
        lines += [
            "## 季度指标",
            "",
            "| 季度 | " + " | ".join(items) + " |",
            "| --- | " + " | ".join("---" for _ in items) + " |",
        ]
        for row in data["quarterly"]:
            cells = [f"{row.get(i, 0):,.3f}" if row.get(i) is not None else "—" for i in items]
            lines.append(f"| {row['quarter']} | " + " | ".join(cells) + " |")
        lines.append("")

    lines += [
        "> 本报告由规则引擎与数据分析生成，用于内部经营分析练习与演示。"
        "分析结论不构成投资建议，涉及判断的事项需回到报表、附注与业务资料核验。",
        "",
    ]
    return "\n".join(lines)


@app.get("/api/report", response_class=PlainTextResponse)
def get_report() -> Response:
    text = _markdown_report(engine.analysis())
    return PlainTextResponse(
        text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="analysis_report.md"'},
    )


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
