"""统一的 Agent 运行器：同一输入接口下运行 MoCA-Agent 或 Financial Agent。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

import llm as llm_module
from financial_agent.benchmark_agent import FinancialNumericAgent
from moca_agent import MoCAFinaAgent


def run_agent_on_sample(agent_kind, sample, cfg):
    """运行单个样本。

    agent_kind: 'moca' | 'fa'
    cfg: {model, temperature, max_tokens, task_prompt, allow_code}
    返回 (answer, trace, elapsed, tokens)
    """
    question, table, context, options = (
        sample["question"], sample.get("table"),
        sample.get("context", ""), sample.get("options"))

    start_idx = len(llm_module.USAGE_LOG)
    t0 = time.time()

    if agent_kind == "moca":
        agent = MoCAFinaAgent(model=cfg.get("model", config.DEFAULT_MODEL),
                              temperature=cfg.get("temperature", config.DEFAULT_TEMPERATURE),
                              max_tokens=cfg.get("max_tokens", config.DEFAULT_MAX_TOKENS),
                              allow_repair=True)
        trace = agent.run(question, table=table, context=context, options=options)
        answer = trace.get("answer")
    else:
        agent = FinancialNumericAgent(
            model=cfg.get("model", config.DEFAULT_MODEL),
            temperature=cfg.get("temperature", config.DEFAULT_TEMPERATURE),
            max_tokens=cfg.get("max_tokens", config.DEFAULT_MAX_TOKENS),
            task_prompt=cfg.get("task_prompt", True),
            allow_code=cfg.get("allow_code", True))
        trace = agent.run(question, table=table, context=context, options=options)
        answer = trace.get("answer")

    elapsed = time.time() - t0
    tokens = _token_delta(start_idx)
    return answer, trace, elapsed, tokens


def _token_delta(start_idx):
    rows = llm_module.USAGE_LOG[start_idx:]
    return {
        "n_calls": len(rows),
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "completion_tokens": sum(r["completion_tokens"] for r in rows),
        "total_tokens": sum(r["total_tokens"] for r in rows),
    }


DEFAULT_CFG = {
    "model": config.DEFAULT_MODEL,
    "temperature": config.DEFAULT_TEMPERATURE,
    "max_tokens": config.DEFAULT_MAX_TOKENS,
}
