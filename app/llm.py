# -*- coding: utf-8 -*-
"""
大模型客户端：只做一件事——把规则命中的信号翻译成「可能原因 + 待核查事项」。

设计原则（这是财务场景和通用问答最大的区别）：
  1. 结论不由模型给出。模型不得改写状态、不得改变阈值判定结果。
  2. 只允许输出「可能原因」和「需要进一步核查的资料」，措辞必须保留不确定性。
  3. 输入只包含信号、口径和阈值，不包含任何原始报表全文，避免模型自由发挥。
  4. 模型输出异常或不可用时，服务降级为「规则结果照常返回」，接口不中断。

只用标准库（urllib），不引入 requests / httpx，减少部署依赖。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

PROVIDERS: dict[str, dict] = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "needs_key": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "needs_key": True,
    },
    "moonshot": {
        "label": "Kimi（月之暗面）",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "needs_key": True,
    },
    "siliconflow": {
        "label": "硅基流动",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "deepseek-ai/DeepSeek-V3",
        "needs_key": True,
    },
    "zhipu": {
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "needs_key": True,
    },
    "ollama": {
        "label": "本地 Ollama",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
        "needs_key": False,
    },
    "custom": {
        "label": "自定义（OpenAI 兼容）",
        "base_url": "",
        "model": "",
        "needs_key": True,
    },
}

SYSTEM_PROMPT = """你是一名企业财务分析助手，服务对象是财务与管理人员。

你只基于给定的规则判定结果工作，不得虚构未提供的科目、金额或事实。

任务：对每一项状态为「关注」或「预警」的指标，给出可能原因和需要进一步核查的资料。

硬性要求：
1. 不要重新判定阈值，不要修改状态，不要新增或删除指标。
2. 原因必须使用「可能」「需要进一步核查」这类表述，禁止把相关性直接写成因果。
3. 禁止推断公司存在舞弊、财务造假、经营危机或违约风险。
4. 禁止给出投资建议、估值判断或买卖结论。
5. 待核查资料要落到实处，写明具体报表或资料，例如「合并现金流量表补充资料」「应收账款账龄表」
   「合同负债明细」「分部报告」「有息负债明细」「受限资金披露」。
6. 只返回 JSON，不要输出解释性文字，不要使用 markdown 代码块。

返回结构：
{
  "summary": "一段话摘要，说明本次共判定多少项、其中多少项需要关注",
  "items": [
    {
      "metric": "指标名称，必须与输入完全一致",
      "status": "关注 或 预警",
      "reading": "用一句话读这个数字，说明它相对阈值意味着什么",
      "possible_causes": ["可能原因1", "可能原因2"],
      "to_verify": ["需要核查的报表或资料1", "需要核查的报表或资料2"]
    }
  ],
  "data_caveats": ["口径或勾稽方面的提示"],
  "next_actions": ["建议的分析动作"]
}"""


class LLMError(RuntimeError):
    """调用大模型失败。"""


def _post(url: str, payload: dict, api_key: str, timeout: int) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise LLMError(f"服务商返回 {e.code}：{detail}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"无法连接模型服务：{e.reason}") from e
    except TimeoutError as e:
        raise LLMError("模型响应超时，请重试或换用更快的模型。") from e


def _extract_json(text: str) -> dict:
    """模型有时会带说明文字或代码块，这里做容错解析。"""
    text = (text or "").strip()
    if not text:
        raise LLMError("模型返回了空内容。")

    if "```" in text:
        for chunk in text.split("```"):
            chunk = chunk.strip()
            if chunk.lower().startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{") and chunk.endswith("}"):
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError:
                    pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise LLMError(f"模型返回的不是合法 JSON（{e.msg}），可重试一次。") from e
    raise LLMError("模型返回内容里没有找到 JSON。")


def explain(
    payload: dict,
    provider: str = "deepseek",
    api_key: str = "",
    model: str = "",
    base_url: str = "",
    timeout: int = 120,
) -> dict:
    """调用大模型生成可能原因与待核查事项。"""
    conf = PROVIDERS.get(provider)
    if conf is None:
        raise LLMError(f"不支持的服务商：{provider}")

    base = (base_url or conf["base_url"]).rstrip("/")
    if not base:
        raise LLMError("自定义服务商需要填写接口地址（OpenAI 兼容的 /v1 地址）。")
    if conf["needs_key"] and not api_key:
        raise LLMError(f"{conf['label']} 需要填写 API Key。Key 只保存在你的浏览器本地。")

    if not payload.get("signals"):
        return {
            "model": model or conf["model"],
            "provider": provider,
            "skipped": True,
            "summary": "本次没有触发关注或预警的指标，无需调用大模型。",
            "items": [],
            "data_caveats": [],
            "next_actions": [],
        }

    user_content = (
        "以下是通过规则引擎判定出的信号，请按系统提示的要求输出 JSON。\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    body = {
        "model": model or conf["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
        "max_tokens": 3000,
    }

    url = f"{base}/chat/completions"
    data = _post(url, body, api_key, timeout)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"模型返回结构异常：{str(data)[:300]}") from e

    try:
        result = _extract_json(content)
    except LLMError:
        # 输出被截断或夹杂说明文字时，定向重试一次
        retry_body = dict(body)
        retry_body["messages"] = body["messages"] + [
            {"role": "assistant", "content": content[:1500]},
            {"role": "user", "content": "上文不是合法 JSON。请只输出一个完整、可解析的 JSON 对象，不要任何其他文字。"},
        ]
        data = _post(url, retry_body, api_key, timeout)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError("重试后模型仍未返回可用内容。") from e
        result = _extract_json(content)

    result["provider"] = provider
    result["model"] = model or conf["model"]
    return result
