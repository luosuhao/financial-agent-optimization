"""统一 Benchmark 输入接口。

固定题目编号与输入格式，保证 MoCA-Agent 与 Financial Agent 使用完全相同的输入。
题目集生成后保存为 experiments/questions/*.json，之后不再变动。
"""
import json
import os
import random

import config

QUESTIONS_DIR = config.BASE_DIR / "experiments" / "questions"
QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)


def load_finqa(path=None):
    path = path or (config.FINQA_DIR / "dev.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_financemath(path=None):
    path = path or (config.FINANCEMATH_DIR / "test.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _table_to_markdown(table):
    if not table:
        return None
    rows = []
    for row in table:
        rows.append("| " + " | ".join(str(c or "") for c in row) + " |")
    return "\n".join(rows)


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def finqa_to_sample(doc, idx=0):
    qa = doc["qa"]
    table = _table_to_markdown(doc.get("table") or doc.get("table_ori"))
    context = " ".join(doc.get("pre_text") or []) + " " + " ".join(doc.get("post_text") or [])
    context = " ".join(context.split())
    return {
        "id": f"finqa_{doc.get('id', str(idx))}-{idx}",
        "dataset": "finqa",
        "question": qa["question"],
        "table": table,
        "context": context,
        "answer": _to_float(qa.get("exe_ans")),
        "answer_str": qa.get("answer"),
        "program": qa.get("program"),
    }


def financemath_to_sample(it):
    tables = "\n\n".join(it.get("tables") or []) or None
    return {
        "id": f"financemath_{it['question_id']}",
        "dataset": "financemath",
        "question": it["question"],
        "table": tables,
        "context": "",
        "answer": float(it["ground_truth"]),
        "answer_str": str(it["ground_truth"]),
        "program": it.get("python_solution"),
        "topic": it.get("topic"),
    }


def _load_all_samples():
    out = []
    for i, doc in enumerate(load_finqa()):
        out.append(finqa_to_sample(doc, i))
    for it in load_financemath():
        out.append(financemath_to_sample(it))
    return out


def build_main_set(n_finqa=20, n_finmath=20, seed=42, force=False):
    """从全部样本中固定采样 n_finqa 个 FinQA + n_finmath 个 FinanceMath。"""
    path = QUESTIONS_DIR / "main_set.json"
    if path.exists() and not force:
        return load_question_set("main_set")
    rng = random.Random(seed)
    all_samples = _load_all_samples()
    finqa = [s for s in all_samples if s["dataset"] == "finqa" and s["answer"] is not None]
    fm = [s for s in all_samples if s["dataset"] == "financemath" and s["answer"] is not None]
    finqa_sel = rng.sample(finqa, n_finqa)
    fm_sel = rng.sample(fm, n_finmath)
    samples = finqa_sel + fm_sel
    for s in samples:
        s["gold_norm"] = s["answer"]
    data = {"seed": seed, "n_finqa": n_finqa, "n_finmath": n_finmath, "samples": samples}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return samples


def build_ablation_set(n_total=24, seed=100, force=False):
    """从主测试集中固定选择题目（含金融数值计算与多步推理为主）。"""
    path = QUESTIONS_DIR / "ablation_set.json"
    if path.exists() and not force:
        return load_question_set("ablation_set")
    main = load_question_set("main_set")
    finqa = [s for s in main if s["dataset"] == "finqa"]
    fm = [s for s in main if s["dataset"] == "financemath"]
    n_f = n_total // 2
    n_m = n_total - n_f
    # 固定选取：取前 n_f 个 FinQA 与前 n_m 个 FinanceMath（确定性）
    sel = finqa[:n_f] + fm[:n_m]
    data = {"seed": seed, "n_total": n_total, "samples": sel}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return sel


def load_question_set(name):
    path = QUESTIONS_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)["samples"]


def sample_to_input(sample):
    """将统一样本转为 Agent 输入 (question, table, context, options)。"""
    return (sample["question"], sample.get("table"), sample.get("context", ""), None)
