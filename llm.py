"""大语言模型统一封装（DeepSeek，OpenAI 兼容接口）。

提供：
- chat(): 一次对话调用，返回文本与 token 用量
- 全局 USAGE_LOG 记录每次调用，用于统计 Avg. Tokens 等指标
- extract_json(): 从模型输出中稳健地抽取 JSON
"""
import json
import re
import time

import config

_client = None
_client_created = False


def _get_client():
    """惰性创建 OpenAI 客户端，避免子进程导入时产生副作用。"""
    global _client, _client_created
    if not _client_created:
        import openai

        _client = openai.OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
            timeout=120,
            max_retries=2,
        )
        _client_created = True
    return _client


USAGE_LOG = []  # 每次调用的 {model, prompt_tokens, completion_tokens, total_tokens, latency, label}


def chat(messages, model=None, temperature=None, max_tokens=None,
         json_mode=False, label="", seed=42, max_retries=4):
    """调用 LLM。

    messages: [{role, content}]
    返回 dict: {text, prompt_tokens, completion_tokens, total_tokens, latency, model, ok}
    """
    model = model or config.DEFAULT_MODEL
    temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature
    max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
    kwargs = dict(model=model, messages=messages, max_tokens=max_tokens,
                  temperature=temperature, seed=seed)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    # deepseek-reasoner 不支持 temperature / seed
    if "reasoner" in model:
        kwargs.pop("temperature", None)
        kwargs.pop("seed", None)

    last_err = None
    for attempt in range(max_retries):
        try:
            t0 = time.time()
            client = _get_client()
            resp = client.chat.completions.create(**kwargs)
            latency = time.time() - t0
            usage = resp.usage
            record = {
                "model": model, "latency": round(latency, 2),
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
                "label": label,
            }
            USAGE_LOG.append(record)
            return {
                "text": resp.choices[0].message.content or "",
                "prompt_tokens": record["prompt_tokens"],
                "completion_tokens": record["completion_tokens"],
                "total_tokens": record["total_tokens"],
                "latency": latency, "model": model, "ok": True,
            }
        except Exception as e:  # 网络/限流等，重试
            last_err = e
            time.sleep(2 * (attempt + 1))
    return {"text": "", "prompt_tokens": 0, "completion_tokens": 0,
            "total_tokens": 0, "latency": 0, "model": model, "ok": False,
            "error": str(last_err)}


def extract_json(text):
    """从模型输出中稳健提取 JSON 对象。"""
    if not text:
        return None
    text = text.strip()
    # 去掉 ```json ... ``` 围栏
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    # 直接尝试
    try:
        return json.loads(text)
    except Exception:
        pass
    # 截取第一对 { } 之间的内容
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            pass
    return None


def extract_first_number(text):
    """从文本中提取第一个数字（含小数、负号、百分号），返回 (数值, 是否为百分比)。"""
    if not text:
        return None, False
    m = re.search(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+\.\d+|-?\d+", text)
    if not m:
        return None, False
    s = m.group(0).replace(",", "")
    is_percent = False
    # 检查数字后是否紧跟 %
    after = text[m.end(): m.end() + 3]
    if "%" in after or "％" in after:
        is_percent = True
    try:
        return float(s), is_percent
    except Exception:
        return None, False


def token_summary():
    total_in = sum(r["prompt_tokens"] for r in USAGE_LOG)
    total_out = sum(r["completion_tokens"] for r in USAGE_LOG)
    n = len(USAGE_LOG)
    return {
        "n_calls": n,
        "prompt_tokens": total_in,
        "completion_tokens": total_out,
        "total_tokens": total_in + total_out,
        "avg_total": round((total_in + total_out) / n, 1) if n else 0,
        "avg_prompt": round(total_in / n, 1) if n else 0,
        "avg_completion": round(total_out / n, 1) if n else 0,
    }
