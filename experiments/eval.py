"""统一评价脚本：计算 Answer Accuracy、Numerical Accuracy、Code Execution Success、
Task Success Rate、Average Time、Token Consumption 等指标。"""
import math


def num_match(pred, gold, tol_rel=0.01, tol_abs=0.01):
    """数值答案判定（含百分号/十进制换算容差）。

    由于部分题目答案存在"百分比 vs 十进制"两种表达（如 12.6% 与 0.126），
    判定时对 pred 尝试 ×100、÷100 三种尺度，任一满足误差即判正确。
    该判定对两个系统一致适用，保证公平。
    """
    if pred is None or gold is None:
        return False
    try:
        pred, gold = float(pred), float(gold)
    except (TypeError, ValueError):
        return False
    if math.isnan(gold):
        return False
    tol = max(tol_abs, tol_rel * abs(gold))
    for scale in (1.0, 100.0, 0.01):
        if abs(pred * scale - gold) <= tol:
            return True
    return False


def parse_pred_answer(raw):
    """从预测记录中解析数值答案。"""
    return raw.get("answer") if isinstance(raw, dict) else raw


def compute_metrics(predictions, golds):
    """predictions: list of dict, golds: list of float。返回指标字典。"""
    n = len(predictions)
    if n == 0:
        return {}
    n_ans_correct = sum(1 for p, g in zip(predictions, golds)
                        if num_match(parse_pred_answer(p), g))
    n_numeric_correct = sum(1 for p, g in zip(predictions, golds)
                            if g is not None and num_match(parse_pred_answer(p), g))
    n_code_ok = sum(1 for p in predictions
                    if p.get("code_success") is True or (
                        p.get("exec") and p["exec"].get("success")))
    n_task_ok = sum(1 for p in predictions if parse_pred_answer(p) is not None)
    times = [p.get("elapsed") or 0 for p in predictions]
    tokens = [p.get("tokens") or {} for p in predictions]
    avg_in = sum(t.get("prompt_tokens", 0) for t in tokens)
    avg_out = sum(t.get("completion_tokens", 0) for t in tokens)
    return {
        "n": n,
        "answer_accuracy": round(n_ans_correct / n, 4),
        "numerical_accuracy": round(n_numeric_correct / n, 4),
        "code_exec_success": round(n_code_ok / n, 4),
        "task_success_rate": round(n_task_ok / n, 4),
        "avg_time": round(sum(times) / n, 2),
        "avg_prompt_tokens": round(avg_in / n, 1),
        "avg_completion_tokens": round(avg_out / n, 1),
        "avg_total_tokens": round((avg_in + avg_out) / n, 1),
        "n_answer_correct": n_ans_correct,
        "n_numeric_correct": n_numeric_correct,
        "n_code_ok": n_code_ok,
        "n_task_ok": n_task_ok,
    }


def fmt_pct(x):
    return f"{x * 100:.2f}%"


def metrics_to_table(m):
    """将指标字典转成 markdown 表格行。"""
    return (f"{m['answer_accuracy'] * 100:.2f}% | {m['numerical_accuracy'] * 100:.2f}% | "
            f"{m['code_exec_success'] * 100:.2f}% | {m['task_success_rate'] * 100:.2f}% | "
            f"{m['avg_time']:.2f}s | {m['avg_total_tokens']:.0f}")
