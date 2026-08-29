"""实验通用工具：Token/时间快照、结果保存加载、进度条。"""
import json
import os
import time

import config


def token_snapshot():
    return len(config and __import__("llm").USAGE_LOG)


def token_delta(start_idx):
    import llm
    rows = llm.USAGE_LOG[start_idx:]
    return {
        "n_calls": len(rows),
        "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
        "completion_tokens": sum(r["completion_tokens"] for r in rows),
        "total_tokens": sum(r["total_tokens"] for r in rows),
    }


def save_json(obj, path):
    path = config.RESULTS_DIR / path if not os.path.isabs(path) else path
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return path


def load_json(path):
    path = config.RESULTS_DIR / path if not os.path.isabs(path) else path
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_prediction(sample, answer, trace, elapsed, token_delta_):
    """将一次运行结果整理为统一预测记录。"""
    exec_ok = False
    if trace:
        if trace.get("exec"):
            exec_ok = bool(trace["exec"].get("success"))
        elif trace.get("exec_result"):
            exec_ok = bool(trace["exec_result"].get("success"))
        elif trace.get("code_success"):
            exec_ok = True
    return {
        "id": sample["id"],
        "dataset": sample.get("dataset"),
        "question": sample.get("question"),
        "gold": sample.get("answer"),
        "gold_str": sample.get("answer_str"),
        "answer": answer,
        "code_success": exec_ok,
        "elapsed": round(elapsed, 2),
        "tokens": token_delta_,
        "has_trace": bool(trace),
    }


def load_partial(run_name):
    """读取已保存的部分预测结果（断点续跑支持）。"""
    path = config.RESULTS_DIR / f"{run_name}_predictions.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        done = {d["id"]: d for d in data}
        return done
    return {}
