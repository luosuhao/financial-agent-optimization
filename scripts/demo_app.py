"""演示用 Streamlit 应用：自动运行四大模块各一个示例，供截图生成报告素材。

用法：streamlit run scripts/demo_app.py --server.port 8599
"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

st.set_page_config(page_title="Financial Agent 演示", layout="wide")

from financial_agent import CodingAgent, FinancialDocQA, MathModeling
from data_analysis import FinancialDataAnalysis

st.title("🧾 Financial Agent — 金融智能体系统（演示）")
st.caption("模块化金融 Agent：Coding Agent · 金融文档问答 · 金融数据分析 · 数学建模")


def show_exec(code, exec_result, figures=None):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**生成代码**")
        st.code(code, language="python")
    with c2:
        st.markdown("**执行日志**")
        out = (exec_result or {}).get("stdout", "") or ""
        err = (exec_result or {}).get("stderr", "") or ""
        st.code(out + (f"\n[stderr] {err}" if err else ""), language="bash")
    for fp in (figures or []):
        if os.path.exists(fp):
            st.image(fp, use_container_width=True)


# ---------------------------------------------------------------- 模块 1
st.header("① Coding Agent — 代码生成与执行")
with st.spinner("Coding Agent 运行中……"):
    agent = CodingAgent()
    rec = agent.run("读取 data/sample_data/示例股票日收盘价.csv（列：日期,收盘价），"
                    "计算日收益率的标准差（日波动率）并输出。")
st.success(f"任务类型：{rec['task_type']} | 执行成功：{rec['success']}")
if rec.get("code"):
    show_exec(rec["code"], rec.get("final_exec"), rec.get("figure_paths"))
st.divider()

# ---------------------------------------------------------------- 模块 2
st.header("② 金融文档问答 — PDF 检索问答")
with st.spinner("解析 PDF、检索证据……"):
    qa = FinancialDocQA()
    qa.load(str(config.PDF_DIR / "示例财务报告.pdf"))
    res = qa.answer("公司2023年的营业收入是多少元？")
st.markdown("**回答：**")
st.write(res["answer"])
if res.get("evidence"):
    st.markdown("**检索到的证据（含页码）：**")
    for e in res["evidence"][:3]:
        st.markdown(f"- 第 **{e['page']}** 页 · {e['type']} · 相似度 {e['score']:.3f}")
        st.code(e["text"][:160], language=None)
st.divider()

# ---------------------------------------------------------------- 模块 3
st.header("③ 金融数据分析 — 指标计算与可视化")
with st.spinner("生成并执行分析代码……"):
    da = FinancialDataAnalysis()
    rec = da.run("计算2022和2023年的营业收入增长率、毛利率，绘制折线图并解释趋势",
                 str(config.SAMPLE_DATA_DIR / "示例公司财务数据.xlsx"))
st.success("分析完成" if rec["success"] else "执行失败")
if rec.get("code"):
    show_exec(rec["code"], rec.get("exec"), rec.get("figures"))
if rec.get("interpretation"):
    st.markdown("**结果解释：**")
    st.markdown(rec["interpretation"][:600])
st.divider()

# ---------------------------------------------------------------- 模块 4
st.header("④ 数学建模 — 投资组合优化")
with st.spinner("数学建模进行中……"):
    mm = MathModeling()
    rec = mm.run("基于 data/sample_data/投资组合日收益率.csv 中沪深300ETF、中证500ETF、国债ETF "
                 "三只资产的日收益率，构建 Markowitz 最小方差投资组合，求权重与年化风险收益。",
                 data_path=str(config.SAMPLE_DATA_DIR / "投资组合日收益率.csv"))
st.success("建模完成" if rec["success"] else "执行失败")
if rec.get("design"):
    with st.expander("建模设计（问题理解/变量/模型/求解方案）", expanded=False):
        st.markdown(rec["design"][:1200])
if rec.get("code"):
    show_exec(rec["code"], rec.get("exec"), rec.get("figures"))
if rec.get("evaluation"):
    st.markdown("**模型评价与结论：**")
    st.markdown(rec["evaluation"][:600])
