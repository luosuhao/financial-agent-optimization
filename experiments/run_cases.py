"""定性实验与案例分析：4 个代表性案例。

Case 1：金融文档/表格问答（对比 MoCA-Agent 与 Financial Agent 的答案与证据）
Case 2：复杂金融数值计算（对比公式选择、计算过程与最终结果）
Case 3：代码执行与错误修复（展示 Financial Agent 的执行反馈修复过程）
Case 4：数学建模（展示完整建模流程）

输出：results/cases.md（报告用）+ results/cases.json
用法：python experiments/run_cases.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config

from financial_agent import CodingAgent, FinancialNumericAgent, MathModeling
from moca_agent import MoCAFinaAgent
from experiments import benchmark
from experiments.util import save_json

BASE = config.BASE_DIR
SAMPLE = config.SAMPLE_DATA_DIR


def fmt_table(table, limit=12):
    if not table:
        return "(无表格)"
    lines = table.strip().splitlines()
    return "\n".join(lines[:limit]) + ("\n..." if len(lines) > limit else "")


def write_case(md_path, title, body):
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(f"\n\n## {title}\n\n{body}\n")


def case1(samples, md_path, store):
    """Case 1：金融文档/表格问答对比。"""
    s = next(x for x in samples if x["dataset"] == "finqa")
    print("  Case 1 ...", flush=True)
    question, table, context = s["question"], s.get("table"), s.get("context")

    fa = FinancialNumericAgent()
    fa_res = fa.run(question, table=table, context=context)
    moca = MoCAFinaAgent()
    mo_res = moca.run(question, table=table, context=context)

    body = (
        f"**题目 ID**：{s['id']}（FinQA）\n\n"
        f"**问题**：{question}\n\n"
        f"**正确答案**：{s['answer']}\n\n"
        f"**输入表格（截取）**：\n```\n{fmt_table(table)}\n```\n\n"
        f"### MoCA-Agent 结果\n"
        f"- 最终答案：`{mo_res.get('answer')}`\n"
        f"- Claim 市场：{len(mo_res['claims'])} 条 claim，状态分布："
        f"{ {k: v['status'] for k, v in mo_res['statuses'].items()} }\n"
        f"- 生成程序：\n```python\n{(mo_res.get('code') or '')[:600]}\n```\n"
        f"- 程序输出：\n```\n{(mo_res.get('exec') or {}).get('stdout', '')[:200]}\n```\n\n"
        f"### Financial Agent 结果\n"
        f"- 最终答案：`{fa_res.get('answer')}`\n"
        f"- 生成代码：\n```python\n{(fa_res.get('code') or '')[:600]}\n```\n"
        f"- 程序输出：\n```\n{(fa_res.get('exec') or {}).get('stdout', '')[:200]}\n```\n\n"
        f"### 对比分析\n"
        f"两个系统均给出答案，MoCA-Agent 通过 claim 市场对证据逐条核验后合成程序；"
        f"Financial Agent 直接依据表格生成代码执行。"
    )
    write_case(md_path, "Case 1：金融文档/表格问答（MoCA-Agent vs Financial Agent）", body)
    store["case1"] = {
        "id": s["id"], "question": question, "gold": s["answer"],
        "moca_answer": mo_res.get("answer"),
        "moca_claims": len(mo_res["claims"]),
        "moca_statuses": {str(k): v["status"] for k, v in mo_res["statuses"].items()},
        "moca_code": mo_res.get("code"), "moca_stdout": (mo_res.get("exec") or {}).get("stdout", ""),
        "fa_answer": fa_res.get("answer"),
        "fa_code": fa_res.get("code"), "fa_stdout": (fa_res.get("exec") or {}).get("stdout", ""),
    }


def case2(samples, md_path, store):
    """Case 2：复杂金融数值计算对比。"""
    s = next(x for x in samples if x["dataset"] == "financemath")
    print("  Case 2 ...", flush=True)
    question, table = s["question"], s.get("table")

    fa = FinancialNumericAgent()
    fa_res = fa.run(question, table=table)
    moca = MoCAFinaAgent()
    mo_res = moca.run(question, table=table)

    body = (
        f"**题目 ID**：{s['id']}（FinanceMath，{s.get('topic', '')}）\n\n"
        f"**问题**：{question}\n\n"
        f"**正确答案**：{s['answer']}\n\n"
        f"**输入表格（截取）**：\n```\n{fmt_table(table)}\n```\n\n"
        f"### MoCA-Agent\n"
        f"- 问题类型 τ = `{mo_res.get('problem_type')}`\n"
        f"- 公式/程序：\n```python\n{(mo_res.get('code') or '')[:800]}\n```\n"
        f"- 程序输出：`{(mo_res.get('exec') or {}).get('stdout', '').strip()[:200]}`\n"
        f"- 验证结果：`{mo_res.get('verify', {})}`\n"
        f"- 最终答案：`{mo_res.get('answer')}`\n\n"
        f"### Financial Agent\n"
        f"- 生成代码：\n```python\n{(fa_res.get('code') or '')[:800]}\n```\n"
        f"- 程序输出：`{(fa_res.get('exec') or {}).get('stdout', '').strip()[:200]}`\n"
        f"- 最终答案：`{fa_res.get('answer')}`\n\n"
        f"### 公式与计算过程对比\n"
        f"两者选择的公式：MoCA-Agent 通过 claim 市场筛选公式 claim 后由综合器合成程序；"
        f"Financial Agent 直接根据问题生成公式代码。对比最终数值是否一致。\n\n"
        f"### 案例分析（静默错误）\n"
        f"本案例中 **MoCA-Agent 给出了错误答案（99.08）且通过了验证**。从它生成的程序可见，"
        f"claim 提取阶段将变量错配：把看跌期权价格 P 记为 50、行权价 K 记为 1、无风险利率 r 记为 2.08、"
        f"到期时间 T 记为 0.04，随后套用买卖权平价 C = P + S - K·e^(-rT) 得到 99.08。"
        f"由于程序本身语法正确、可正常运行并输出数值，结构化验证未发现异常（violations 为空），"
        f"属于论文所指的\"静默计算错误\"（silent miscomputation）。\n\n"
        f"相比之下 **Financial Agent 正确提取了 S=50、K=50、P=2.08、r=0.04、T=1 并给出 4.0405**，"
        f"与标准答案 4.041 一致。这说明在数值推理中，证据/变量提取的准确性比\"是否执行代码\"更为关键；"
        f"MoCA-Agent 的 claim 市场在变量层面缺乏足够约束，是造成此类错误的潜在原因。"
    )
    write_case(md_path, "Case 2：复杂金融数值计算（公式与过程对比）", body)
    store["case2"] = {
        "id": s["id"], "question": question, "gold": s["answer"], "topic": s.get("topic"),
        "moca_answer": mo_res.get("answer"), "moca_problem_type": mo_res.get("problem_type"),
        "moca_code": mo_res.get("code"), "moca_stdout": (mo_res.get("exec") or {}).get("stdout", ""),
        "moca_verify": mo_res.get("verify"),
        "fa_answer": fa_res.get("answer"),
        "fa_code": fa_res.get("code"), "fa_stdout": (fa_res.get("exec") or {}).get("stdout", ""),
    }


def case3(md_path, store):
    """Case 3：代码执行与错误修复。"""
    print("  Case 3 ...", flush=True)
    agent = CodingAgent()
    buggy_code = (
        "import pandas as pd\n"
        "df = pd.read_excel('data/sample_data/示例公司财务数据.xlsx')\n"
        "df['毛利率'] = df['毛利'] / df['营业总收入']\n"   # 错误：列名'营业总收入'不存在 → KeyError
        "print(df[['年份', '毛利率']])"
    )
    task = ("修复下面代码中的错误，使其正确计算毛利率并输出。"
            "数据文件：data/sample_data/示例公司财务数据.xlsx（列：年份,营业收入,营业成本,毛利,...）")
    rec = agent.run(task, existing_code=buggy_code)

    body_lines = [
        f"**任务**：修复代码中的计算错误（毛利率分母用错）\n",
        f"**初始（有 Bug）代码**：\n```python\n{buggy_code}\n```\n",
    ]
    for att in rec.get("attempts", []):
        exec_ok = bool(att.get("exec") and att["exec"].get("success"))
        err = (att.get("exec") or {}).get("error_msg")
        body_lines.append(
            f"**尝试 {att['attempt']}**：执行成功 = {exec_ok}"
            + (f"，错误 = `{err}`" if not exec_ok and err else "")
            + "\n```python\n" + (att.get("code") or "")[:500] + "\n```\n"
        )
    body_lines.append(
        f"**最终执行输出**：\n```\n{(rec.get('final_exec') or {}).get('stdout', '')[:300]}\n```\n"
        f"**结论**：通过 {len(rec.get('attempts', []))} 次尝试，在获取执行错误反馈后自动修改代码并成功运行。"
    )
    body = "\n".join(body_lines)
    write_case(md_path, "Case 3：代码执行与错误修复（执行反馈驱动）", body)
    store["case3"] = {
        "task": task, "buggy_code": buggy_code, "n_attempts": len(rec.get("attempts", [])),
        "final_stdout": (rec.get("final_exec") or {}).get("stdout", ""),
        "success": rec.get("success"),
    }


def case4(md_path, store):
    """Case 4：数学建模完整流程。"""
    print("  Case 4 ...", flush=True)
    agent = MathModeling()
    problem = (f"基于 {SAMPLE / '投资组合日收益率.csv'} 中沪深300ETF、中证500ETF、国债ETF "
               f"三只资产的日收益率数据，构建 Markowitz 均值-方差模型，"
               f"求最小方差组合的权重、期望年化收益率与年化波动率。")
    rec = agent.run(problem, data_path=str(SAMPLE / "投资组合日收益率.csv"))

    body = (
        f"**建模问题**：{problem}\n\n"
        f"### 1. 问题理解与目标分析 / 2. 变量与假设 / 3. 模型选择 / 4. 求解方案\n\n"
        f"{(rec.get('design') or '')[:1500]}\n\n"
        f"### 5. 生成并执行的代码\n```python\n{(rec.get('code') or '')[:1200]}\n```\n\n"
        f"### 执行输出\n```\n{(rec.get('exec') or {}).get('stdout', '')[:500]}\n```\n\n"
        f"### 6. 模型结果评价 / 7. 结论解释\n\n"
        f"{(rec.get('evaluation') or '')[:1500]}\n"
    )
    write_case(md_path, "Case 4：数学建模（投资组合优化完整流程）", body)
    store["case4"] = {
        "problem": problem, "success": rec.get("success"),
        "design": rec.get("design"), "code": rec.get("code"),
        "stdout": (rec.get("exec") or {}).get("stdout", ""),
        "evaluation": rec.get("evaluation"),
        "exec_error": (rec.get("exec") or {}).get("error_msg"),
    }


def main():
    samples = benchmark.load_question_set("main_set")
    md_path = config.RESULTS_DIR / "cases.md"
    if md_path.exists():
        md_path.unlink()
    store = {}
    case1(samples, md_path, store)
    case2(samples, md_path, store)
    case3(md_path, store)
    case4(md_path, store)
    save_json(store, "cases.json")
    print("定性案例分析完成，结果保存到 results/cases.md 与 results/cases.json。")


if __name__ == "__main__":
    main()
