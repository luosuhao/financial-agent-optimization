"""Financial Agent 扩展能力实验（仅测试 Financial Agent，不与 MoCA-Agent 对比）：
1. Coding Agent 测试（6 个任务：代码生成2 / 代码理解2 / Bug修复2）
2. 端到端金融 PDF 问答（示例年报 + 分红公告，各 3-5 问）
3. 数学建模测试（信用风险评价 / 投资组合优化 / 收益预测 / 企业综合评价）

用法：python experiments/run_extension.py [--skip-coding|--skip-pdf|--skip-modeling] [--smoke]
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

from financial_agent import CodingAgent, FinancialDocQA, MathModeling
from experiments.util import save_json, load_json
from experiments.finparse import parse_financial_number, match_financial_answer

BASE = config.BASE_DIR
SAMPLE = config.SAMPLE_DATA_DIR
PDF = config.PDF_DIR

# ---------------------------------------------------------------- Coding 任务
CODING_TASKS = [
    {"id": "coding_gen_1", "type": "generate",
     "task": (f"读取数据文件 {SAMPLE / '示例股票日收盘价.csv'}（列为：日期,收盘价），"
              f"计算该股票的日收益率序列，并输出日收益率的标准差（日波动率）。")},
    {"id": "coding_gen_2", "type": "generate",
     "task": (f"读取数据文件 {SAMPLE / '示例公司财务数据.xlsx'}（Sheet 为'财务数据'，列为：年份,营业收入,...），"
              f"计算 2022 年和 2023 年的营业收入增长率，并分别输出（保留4位小数）。")},
    {"id": "coding_explain_1", "type": "explain",
     "task": "请解释下面这段代码的功能",
     "code": ("import pandas as pd\n"
              "df = pd.read_csv('data.csv')\n"
              "df['ret'] = df['close'].pct_change()\n"
              "print(df['ret'].std() * (252**0.5))")},
    {"id": "coding_explain_2", "type": "explain",
     "task": "请解释下面这段代码的功能",
     "code": ("import numpy as np\n"
              "def sharpe(returns, rf=0.0):\n"
              "    excess = returns - rf/252\n"
              "    return np.mean(excess)/np.std(excess)*np.sqrt(252)\n"
              "print(sharpe(np.array([0.01,-0.005,0.02,0.008])))")},
    {"id": "coding_fix_1", "type": "fix",
     "task": ("修复下面代码中的错误，使其能够正确计算并输出。"
              f"数据文件为 {SAMPLE / '示例公司财务数据.xlsx'}，列名：年份,营业收入,营业成本,毛利,净利润,总资产,总负债,所有者权益。"),
     "code": ("import pandas as pd\n"
              "df = pd.read_excel('示例公司财务数据.xlsx')\n"
              "df['毛利率'] = df['毛利'] / df['营业成本']\n"   # 错误：应为营业收入
              "print(df[['年份','毛利率']])")},
    {"id": "coding_fix_2", "type": "fix",
     "task": "修复下面代码中的错误，使其能够正确运行并输出结果。",
     "code": ("import numpy as np\n"
              "a = np.array([1, 2, 3])\n"
              "b = np.array([4, 5, 6])\n"
              "print(a @ b)\n"
              "c = np.dot(a, b)\n"
              "print(\"dot =\", c)\n"
              "print(\"sum =\", a.sum))")},   # 错误：a.sum 缺少括号
]


def run_coding(agent, smoke=False):
    import time
    import llm as llm_module
    tasks = CODING_TASKS[:2] if smoke else CODING_TASKS
    results = []
    for t in tasks:
        print(f"  Coding 任务 {t['id']} ...", flush=True)
        start_tokens = len(llm_module.USAGE_LOG)
        t0 = time.time()
        try:
            rec = agent.run(t["task"], existing_code=t.get("code"))
            elapsed = time.time() - t0
            token_rows = llm_module.USAGE_LOG[start_tokens:]
            tokens = {
                "n_calls": len(token_rows),
                "prompt_tokens": sum(r["prompt_tokens"] for r in token_rows),
                "completion_tokens": sum(r["completion_tokens"] for r in token_rows),
                "total_tokens": sum(r["total_tokens"] for r in token_rows),
            }
            ttype = rec.get("task_type")
            if ttype == "explain":
                exec_ok = None  # 代码理解任务不涉及执行
            else:
                exec_ok = bool(rec.get("final_exec") and rec["final_exec"].get("success"))
            fixed_after_error = len(rec.get("attempts", [])) > 1
            results.append({
                "id": t["id"], "type": ttype, "success": rec.get("success"),
                "code_exec_success": exec_ok, "repaired_after_error": fixed_after_error,
                "n_attempts": len(rec.get("attempts", [])),
                "elapsed": round(elapsed, 2), "tokens": tokens,
                "task": t["task"], "code": rec.get("code"),
                "stdout": (rec.get("final_exec") or {}).get("stdout", ""),
                "explanation": rec.get("explanation"),
                "error": (rec.get("final_exec") or {}).get("error_msg"),
            })
        except Exception as e:
            results.append({"id": t["id"], "type": t["type"], "success": False,
                            "code_exec_success": False, "repaired_after_error": False,
                            "n_attempts": 0, "task": t["task"], "error": str(e)})
        save_json(results, "ext_coding.json")
    return results


def summarize_coding(results):
    n = len(results)
    exec_tasks = [r for r in results if r.get("code_exec_success") is not None]
    exec_ok = sum(1 for r in exec_tasks if r.get("code_exec_success"))
    task_ok = sum(1 for r in results if r.get("success"))
    repaired = sum(1 for r in results if r.get("repaired_after_error"))
    return {
        "n": n, "n_exec_tasks": len(exec_tasks),
        "code_exec_success_rate": round(exec_ok / len(exec_tasks), 4) if exec_tasks else None,
        "task_success_rate": round(task_ok / n, 4) if n else 0,
        "n_repaired_after_error": repaired,
    }


# ---------------------------------------------------------------- PDF 问答
PDF_QA_SETS = [
    {"pdf": PDF / "示例财务报告.pdf", "questions": [
        {"q": "公司2023年的营业收入是多少元？", "gold": 3584000000.0,
         "gold_str": "3,584,000,000", "page": 2, "metric": "numeric"},
        {"q": "公司2023年的毛利率是多少？", "gold": 0.3499, "gold_str": "34.99%",
         "page": 3, "metric": "numeric"},
        {"q": "2023年归属于上市公司股东的净利润同比增长了多少？", "gold": 0.1707,
         "gold_str": "17.07%", "page": 2, "metric": "numeric"},
        {"q": "公司2022年的总资产是多少元？", "gold": 4600000000.0,
         "gold_str": "4,600,000,000", "page": 2, "metric": "numeric"},
        {"q": "公司研发投入占营业收入的比重是多少？", "gold": 0.1702,
         "gold_str": "17.02%", "page": 3, "metric": "numeric"},
    ]},
    {"pdf": PDF / "示例分红公告.pdf", "questions": [
        {"q": "公司2023年度每10股派发现金红利多少元（含税）？", "gold": 4.50,
         "gold_str": "4.50", "page": 1, "metric": "numeric"},
        {"q": "公司本次权益分派的股权登记日是哪一天？", "gold": "2024-05-20",
         "gold_str": "2024-05-20", "page": 2, "metric": "text"},
        {"q": "公司2023年度派发现金红利总额是多少元？", "gold": 112500000.0,
         "gold_str": "112,500,000", "page": 2, "metric": "numeric"},
    ]},
]


def _num_match(pred, gold):
    from experiments.eval import num_match
    if isinstance(gold, (int, float)):
        return num_match(pred, gold)
    return False


def _text_match(answer, gold):
    """宽松文本匹配：比较答案与标准答案中的数字片段（容忍日期/数量表述差异）。"""
    if not answer:
        return False
    if gold in answer:
        return True
    g_digits = set(re.findall(r"\d+", str(gold)))
    a_digits = set(re.findall(r"\d+", answer))
    if not g_digits:
        return False
    # 答案须包含标准答案的全部数字片段
    return g_digits.issubset(a_digits)


def run_pdf_qa(agent, smoke=False):
    all_results = []
    for ds in PDF_QA_SETS:
        qs = ds["questions"][:1] if smoke else ds["questions"]
        print(f"  文档 {ds['pdf'].name} ...", flush=True)
        agent.load(str(ds["pdf"]))
        for q in qs:
            try:
                r = agent.answer(q["q"])
                ans = r["answer"]
                ev_pages = [e["page"] for e in r.get("evidence", [])]
                correct = False
                if q["metric"] == "numeric":
                    correct = match_financial_answer(ans, q["gold"])
                else:
                    correct = _text_match(ans, q["gold"])
                ev_hit = q["page"] in ev_pages
                source_ok = str(q["page"]) in ans
                all_results.append({
                    "pdf": ds["pdf"].name, "question": q["q"], "answer": ans,
                    "gold": q["gold_str"], "gold_value": q["gold"],
                    "metric": q["metric"], "correct": correct,
                    "evidence_hit": ev_hit, "evidence_pages": ev_pages,
                    "source_page_ok": source_ok,
                    "gold_page": q["page"],
                })
            except Exception as e:
                all_results.append({"pdf": ds["pdf"].name, "question": q["q"],
                                    "answer": None, "gold": q["gold_str"],
                                    "correct": False, "evidence_hit": False,
                                    "source_page_ok": False, "error": str(e)})
            save_json(all_results, "ext_pdfqa.json")
    return all_results


def summarize_pdfqa(results):
    n = len(results)
    return {
        "n": n,
        "answer_accuracy": round(sum(1 for r in results if r.get("correct")) / n, 4) if n else 0,
        "evidence_hit_rate": round(sum(1 for r in results if r.get("evidence_hit")) / n, 4) if n else 0,
        "source_page_rate": round(sum(1 for r in results if r.get("source_page_ok")) / n, 4) if n else 0,
    }


# ---------------------------------------------------------------- 数学建模
MODELING_TASKS = [
    {"id": "modeling_1", "title": "信用风险评价",
     "problem": (f"基于 {SAMPLE / '企业信用评价示例数据.csv'} 中各企业的流动比率、速动比率、"
                 f"资产负债率、营业收入增长率、净利润增长率、ROA、ROE、销售毛利率等指标，"
                 f"采用综合评价方法（如熵权法+TOPSIS）计算各企业的信用风险综合得分并排序，"
                 f"识别信用风险最高的企业。"),
     "data": str(SAMPLE / "企业信用评价示例数据.csv")},
    {"id": "modeling_2", "title": "投资组合优化",
     "problem": (f"基于 {SAMPLE / '投资组合日收益率.csv'} 中沪深300ETF、中证500ETF、国债ETF "
                 f"三只资产的日收益率数据，构建 Markowitz 均值-方差模型，"
                 f"求最小方差投资组合的权重、期望年化收益率与年化波动率。"),
     "data": str(SAMPLE / "投资组合日收益率.csv")},
    {"id": "modeling_3", "title": "收益预测",
     "problem": (f"基于 {SAMPLE / '示例股票日收盘价.csv'} 的历史收盘价，"
                 f"使用线性回归或时间序列方法拟合价格趋势并预测下一个交易日的收盘价，"
                 f"给出预测值并评价模型（如 R²、均方误差）。"),
     "data": str(SAMPLE / "示例股票日收盘价.csv")},
    {"id": "modeling_4", "title": "企业综合评价",
     "problem": (f"基于 {SAMPLE / '企业信用评价示例数据.csv'} 中 10 家企业的多项财务指标，"
                 f"采用加权综合评分法（指标正向化、无量纲化后加权求和）对企业进行综合评价排名，"
                 f"分析得分构成。"),
     "data": str(SAMPLE / "企业信用评价示例数据.csv")},
]


def run_modeling(agent, smoke=False):
    tasks = MODELING_TASKS[:1] if smoke else MODELING_TASKS
    results = []
    for t in tasks:
        print(f"  建模任务 {t['id']} ({t['title']}) ...", flush=True)
        try:
            rec = agent.run(t["problem"], data_path=t["data"])
            results.append({
                "id": t["id"], "title": t["title"], "problem": t["problem"],
                "success": rec.get("success"),
                "design": rec.get("design"), "code": rec.get("code"),
                "exec_success": bool(rec.get("exec") and rec["exec"].get("success")),
                "stdout": (rec.get("exec") or {}).get("stdout", ""),
                "evaluation": rec.get("evaluation"),
                "error": (rec.get("exec") or {}).get("error_msg"),
                "figures": rec.get("figures", []),
            })
        except Exception as e:
            results.append({"id": t["id"], "title": t["title"], "problem": t["problem"],
                            "success": False, "exec_success": False, "error": str(e)})
        save_json(results, "ext_modeling.json")
    return results


def summarize_modeling(results):
    return {
        "n": len(results),
        "code_exec_success_rate": round(sum(1 for r in results if r.get("exec_success")) / len(results), 4)
        if results else 0,
        "task_success_rate": round(sum(1 for r in results if r.get("success")) / len(results), 4)
        if results else 0,
    }


def reeval_pdfqa():
    """读取已保存的 ext_pdfqa.json，用改进的数字解析器重新计算正确率（无需再次调用 LLM）。"""
    results = load_json("ext_pdfqa.json")
    if not results:
        print("没有 ext_pdfqa.json，先运行 PDF 问答实验。")
        return
    for r in results:
        if r.get("metric") == "numeric" and r.get("gold_value") is not None:
            r["correct"] = match_financial_answer(r.get("answer", ""), r["gold_value"])
        else:
            r["correct"] = _text_match(r.get("answer", ""), r.get("gold", ""))
    save_json(results, "ext_pdfqa.json")
    s = summarize_pdfqa(results)
    print("重评后 PDF QA:", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-coding", action="store_true")
    ap.add_argument("--skip-pdf", action="store_true")
    ap.add_argument("--skip-modeling", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--reeval-pdfqa", action="store_true")
    args = ap.parse_args()

    if args.reeval_pdfqa:
        reeval_pdfqa()
        return

    summary = {}

    if not args.skip_coding:
        print("===== 扩展实验 1：Coding Agent 测试 =====")
        agent = CodingAgent()
        res = run_coding(agent, smoke=args.smoke)
        s = summarize_coding(res)
        summary["coding"] = s
        print("  Coding 结果:", s)

    if not args.skip_pdf:
        print("\n===== 扩展实验 2：端到端金融 PDF 问答 =====")
        agent = FinancialDocQA()
        res = run_pdf_qa(agent, smoke=args.smoke)
        s = summarize_pdfqa(res)
        summary["pdfqa"] = s
        print("  PDF QA 结果:", s)

    if not args.skip_modeling:
        print("\n===== 扩展实验 3：数学建模测试 =====")
        agent = MathModeling()
        res = run_modeling(agent, smoke=args.smoke)
        s = summarize_modeling(res)
        summary["modeling"] = s
        print("  建模结果:", s)

    save_json(summary, "ext_summary.json")
    print("\n扩展能力实验完成，结果已保存到 results/ 目录。")


if __name__ == "__main__":
    main()
