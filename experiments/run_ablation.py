"""消融实验：w/o Task-specific Prompt、w/o Code Execution、Full Financial Agent。

在固定消融题集（从主测试集中选取，含数值计算与多步推理为主）上运行 Financial Agent。
用法：python experiments/run_ablation.py [--smoke N] [--resume]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

from experiments import benchmark
from experiments.eval import compute_metrics
from experiments.runner import run_agent_on_sample, DEFAULT_CFG
from experiments.util import save_json, load_partial

VARIANTS = [
    ("wo_task_prompt", "w/o Task-specific Prompt", dict(task_prompt=False, allow_code=True)),
    ("wo_code", "w/o Code Execution", dict(task_prompt=True, allow_code=False)),
    ("full", "Full Financial Agent", dict(task_prompt=True, allow_code=True)),
]


def run_variant(vname, vlabel, vcfg, samples, resume=True):
    cfg = dict(DEFAULT_CFG)
    cfg.update(vcfg)
    run_name = f"ablation_{vname}"
    done = load_partial(run_name) if resume else {}
    preds = []
    total = len(samples)
    for i, sample in enumerate(samples):
        sid = sample["id"]
        if sid in done:
            preds.append(done[sid])
            continue
        print(f"  [{i+1}/{total}] {vlabel} {sid} ...", flush=True)
        try:
            answer, trace, elapsed, tokens = run_agent_on_sample("fa", sample, cfg)
            rec = {"id": sid, "dataset": sample["dataset"],
                   "question": sample["question"], "gold": sample["answer"],
                   "gold_str": sample.get("answer_str"), "answer": answer,
                   "code_success": bool(trace.get("exec") and trace["exec"].get("success")),
                   "elapsed": round(elapsed, 2), "tokens": tokens}
        except Exception as e:
            rec = {"id": sid, "dataset": sample["dataset"],
                   "question": sample["question"], "gold": sample["answer"],
                   "gold_str": sample.get("answer_str"), "answer": None,
                   "code_success": False, "elapsed": 0, "tokens": {}, "error": str(e)}
        preds.append(rec)
        save_json(preds, f"{run_name}_predictions.json")
    return preds


def aggregate(samples, preds):
    pmap = {p["id"]: p for p in preds}
    res = {}
    for ds in ("finqa", "financemath"):
        ps = [pmap[s["id"]] for s in samples if s["id"] in pmap and s["dataset"] == ds]
        gs = [s["answer"] for s in samples if s["id"] in pmap and s["dataset"] == ds]
        if ps:
            res[ds] = compute_metrics(ps, gs)
    ps = [pmap[s["id"]] for s in samples if s["id"] in pmap]
    gs = [s["answer"] for s in samples if s["id"] in pmap]
    res["overall"] = compute_metrics(ps, gs)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    samples = benchmark.build_ablation_set(config.ABLATION_N_TOTAL, seed=100)
    if args.smoke:
        samples = samples[:args.smoke]
    print(f"消融题集规模：{len(samples)} 题")

    summary = {"question_set": "ablation_set", "variants": {}}
    for vname, vlabel, vcfg in VARIANTS:
        print(f"\n===== 消融变体：{vlabel} =====")
        preds = run_variant(vname, vlabel, vcfg, samples, resume=args.resume)
        agg = aggregate(samples, preds)
        summary["variants"][vname] = {"label": vlabel, "metrics": agg}
        save_json(agg, f"ablation_{vname}_metrics.json")
        o = agg.get("overall", {})
        print(f"  Overall Acc {o.get('answer_accuracy', 0)*100:.2f}% | "
              f"TaskOK {o.get('task_success_rate', 0)*100:.2f}% | "
              f"Time {o.get('avg_time', 0):.2f}s | Tokens {o.get('avg_total_tokens', 0):.0f}")

    save_json(summary, "ablation_summary.json")
    print("\n消融实验完成，结果已保存到 results/ 目录。")


if __name__ == "__main__":
    main()
