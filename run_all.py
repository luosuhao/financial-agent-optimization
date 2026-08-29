"""一键运行全部实验（依次执行）。

用法：python run_all.py [--skip-main] [--skip-ablation] [--skip-extension] [--skip-cases]
"""
import argparse
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("主对比实验", "experiments/run_main.py", "skip_main"),
    ("消融实验", "experiments/run_ablation.py", "skip_ablation"),
    ("扩展能力实验", "experiments/run_extension.py", "skip_extension"),
    ("定性案例分析", "experiments/run_cases.py", "skip_cases"),
]


def main():
    ap = argparse.ArgumentParser()
    for _, _, attr in STEPS:
        ap.add_argument(f"--{attr}", action="store_true")
    args = ap.parse_args()
    for label, script, attr in STEPS:
        if getattr(args, attr):
            print(f"跳过：{label}", flush=True)
            continue
        print(f"\n{'='*60}\n开始：{label}（{script}）\n{'='*60}", flush=True)
        rc = subprocess.run([sys.executable, script], cwd=BASE)
        if rc.returncode != 0:
            print(f"[WARN] {label} 返回码 {rc.returncode}，继续下一项", flush=True)
    print("\n全部实验完成。")


if __name__ == "__main__":
    main()
