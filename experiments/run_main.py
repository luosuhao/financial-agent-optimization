"""主对比实验：MoCA-Agent vs Financial Agent（FinQA 20 题 + FinanceMath 20 题）。

用法：
  python experiments/run_main.py [--smoke N] [--resume] [--agent moca|fa|all]
  --smoke N 仅运行前 N 题（冒烟测试）
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

from experiments import benchmark
from experiments.eval import compute_metrics
from experiments.runner import run_agent_on_sample, DEFAULT_CFG
from experiments.util import save_json, load_partial

AGENTS = {"moca": "MoCA-Agent", "fa": "Financial Agent"}


def run_experiment(agent_kind, samples, cfg, run_name, resume=True):
    done = load_partial(run_name) if resume else {}
    predictions = []
    todo = [s for s in samples if s["id"] not in done]
    total = len(samples)
    print(f"[{AGENTS[agent_kind]}] 待运行 {len(todo)}/{total}")
    for i, sample in enumerate(samples):
        sid = sample["id"]
        if sid in done:
            predictions.append(done[sid])
            continue
        print(f"  [{i+1}/{total}] {agent_kind} {sid} 开始...", flush=True)
        try:
            answer, trace, elapsed, tokens = run_agent_on_sample(agent_kind, sample, cfg)
            rec = {
                "id": sid, "dataset": sample["dataset"],
                "question": sample["question"],
                "gold": sample["answer"], "gold_str": sample.get("answer_str"),
                "answer": answer,
                "code_success": bool(trace.get("exec") and trace["exec"].get("success")),
                "elapsed": round(elapsed, 2), "tokens": tokens,
            }
        except Exception as e:
            print(f"    运行异常: {e}")
            rec = {"id": sid, "dataset": sample["dataset"],
                   "question": sample["question"], "gold": sample["answer"],
                   "gold_str": sample.get("answer_str"), "answer": None,
                   "code_success": False, "elapsed": 0, "tokens": {},
                   "error": str(e)}
        predictions.append(rec)
        # 增量保存
        save_json(predictions, f"{run_name}_predictions.json")
        if (i + 1) % 5 == 0 or (i + 1) == total:
            print(f"    进度 {i+1}/{total}", flush=True)
    return predictions


def aggregate(samples, predictions):
    """分别按 FinQA / FinanceMath / 整体 计算指标。"""
    pmap = {p["id"]: p for p in predictions}
    by_ds = {"finqa": [], "financemath": []}
    golds = {"finqa": [], "financemath": []}
    for s in samples:
        p = pmap.get(s["id"])
        if p is None:
            continue
        by_ds[s["dataset"]].append(p)
        golds[s["dataset"]].append(s["answer"])
    overall_pred = [pmap[s["id"]] for s in samples if s["id"] in pmap]
    overall_gold = [s["answer"] for s in samples if s["id"] in pmap]
    res = {}
    for ds in ("finqa", "financemath"):
        if by_ds[ds]:
            res[ds] = compute_metrics(by_ds[ds], golds[ds])
    res["overall"] = compute_metrics(overall_pred, overall_gold)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=0, help="仅运行前 N 题")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--agent", default="all", choices=["moca", "fa", "all"])
    args = ap.parse_args()

    samples = benchmark.build_main_set(config.MAIN_N_FINQA, config.MAIN_N_FINANCEMATH, seed=42)
    if args.smoke:
        samples = samples[:args.smoke]
    print(f"测试集规模：FinQA {config.MAIN_N_FINQA} + FinanceMath {config.MAIN_N_FINANCEMATH}，"
          f"本次运行 {len(samples)} 题")

    cfg = dict(DEFAULT_CFG)
    results = {"config": cfg, "question_set": "main_set", "per_agent": {}}

    for agent_kind in ("moca", "fa"):
        if args.agent != "all" and args.agent != agent_kind:
            continue
        run_name = f"main_{agent_kind}"
        preds = run_experiment(agent_kind, samples, cfg, run_name, resume=args.resume)
        agg = aggregate(samples, preds)
        results["per_agent"][agent_kind] = agg
        save_json(agg, f"{run_name}_metrics.json")
        _print_metrics(agent_kind, agg)

    save_json(results, "main_summary.json")
    print("\n主对比实验结果已保存到 results/ 目录。")


def _print_metrics(name, agg):
    print(f"\n===== {AGENTS.get(name, name)} 主对比结果 =====")
    for ds, m in agg.items():
        if not m:
            continue
        print(f"[{ds}] Acc {m['answer_accuracy']*100:.2f}% | "
              f"NumAcc {m['numerical_accuracy']*100:.2f}% | "
              f"CodeExec {m['code_exec_success']*100:.2f}% | "
              f"TaskOK {m['task_success_rate']*100:.2f}% | "
              f"Time {m['avg_time']:.2f}s | Tokens {m['avg_total_tokens']:.0f}")


if __name__ == "__main__":
    main()
