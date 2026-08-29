"""Financial Agent Web 界面（Streamlit）。

运行：streamlit run app.py
包含四个功能模块：Coding Agent / 金融文档问答 / 金融数据分析 / 数学建模。
侧边栏可切换模型参数与消融开关（任务专用 Prompt、代码执行）。
"""
import os
import sys

import streamlit as st

import config
import llm as llm_module

st.set_page_config(page_title="Financial Agent · 金融智能体系统", layout="wide")

# 保证在 Streamlit 下可导入项目模块
BASE = config.BASE_DIR
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from financial_agent import CodingAgent, FinancialDocQA, MathModeling
from data_analysis import FinancialDataAnalysis

# ------------------------------------------------------------------ 侧边栏
with st.sidebar:
    st.title("⚙️ 系统设置")
    api_key = st.text_input("DeepSeek API Key", value=config.DEEPSEEK_API_KEY,
                            type="password", help="默认读取 .env")
    if api_key and api_key != config.DEEPSEEK_API_KEY:
        config.DEEPSEEK_API_KEY = api_key
        # 同步到环境变量，保证独立 data_analysis 包读取到新 Key
        os.environ["DEEPSEEK_API_KEY"] = api_key
    model = st.selectbox("模型", ["deepseek-chat", "deepseek-reasoner"],
                         index=0 if config.DEFAULT_MODEL == "deepseek-chat" else 1)
    temperature = st.slider("Temperature", 0.0, 1.0, config.DEFAULT_TEMPERATURE, 0.1)
    max_tokens = st.number_input("最大输出 Token", 256, 8192, config.DEFAULT_MAX_TOKENS, 64)
    st.divider()
    st.subheader("消融开关（实验用）")
    use_task_prompt = st.toggle("任务专用 Prompt", value=config.DEFAULT_TASK_PROMPT,
                                help="关闭后统一使用普通金融助手 Prompt（w/o Task-specific Prompt）")
    allow_code = st.toggle("允许执行 Python 代码", value=config.DEFAULT_ALLOW_CODE,
                           help="关闭后仅由 LLM 直接推理（w/o Code Execution）")
    st.divider()
    if st.button("查看 Token 用量统计"):
        s = llm_module.token_summary()
        st.json(s)

st.title("🧾 Financial Agent — 金融智能体系统")
st.caption("模块化金融 Agent：Coding Agent · 金融文档问答 · 金融数据分析 · 数学建模（参考 MoCA-Agent 流程）")

tab = st.sidebar.radio("功能模块", ["Coding Agent", "金融文档问答", "金融数据分析", "数学建模"])

_save_dir = config.SAMPLE_DATA_DIR / "uploads"
_save_dir.mkdir(parents=True, exist_ok=True)


def _save_upload(uploaded):
    if uploaded is None:
        return None
    p = _save_dir / uploaded.name
    with open(p, "wb") as f:
        f.write(uploaded.getbuffer())
    return str(p)


def _show_exec(code, exec_result, figures=None):
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("生成代码")
        st.code(code, language="python")
    with c2:
        st.subheader("执行日志")
        out = exec_result.get("stdout", "") if exec_result else ""
        err = exec_result.get("stderr", "") if exec_result else ""
        if exec_result and exec_result.get("error_type"):
            st.error(f"{exec_result['error_type']}: {exec_result['error_msg']}")
        st.code(out + ("\n" + err if err else ""), language="bash")
    if figures:
        st.subheader("可视化结果")
        for fp in figures:
            if os.path.exists(fp):
                st.image(fp, use_container_width=True)


# ================================================================ Coding Agent
if tab == "Coding Agent":
    st.subheader("🤖 Coding Agent")
    st.write("根据自然语言任务生成、理解、修改并执行 Python 代码；支持基于运行错误自动修复重试。")
    task = st.text_area("任务描述", height=100,
                        placeholder="例如：计算某公司过去三年营业收入的平均增长率；或 解释/修改/修复 一段代码")
    col1, col2 = st.columns(2)
    with col1:
        uploaded = st.file_uploader("上传数据文件（可选）", type=["csv", "xlsx", "xls"])
    with col2:
        existing = st.text_area("已有代码（可选，用于解释/修改/修复）", height=120)
    if st.button("运行", key="run_coding", type="primary"):
        if not task.strip():
            st.warning("请输入任务描述")
        else:
            data_path = _save_upload(uploaded)
            agent = CodingAgent(model=model, temperature=temperature,
                                max_tokens=int(max_tokens), task_prompt=use_task_prompt,
                                allow_code=allow_code)
            with st.spinner("Coding Agent 运行中……"):
                rec = agent.run(task.strip(), existing_code=existing or None,
                                file_path=data_path)
            st.success(f"任务类型：{rec['task_type']} | 执行成功：{rec['success']}")
            st.json({"task_type": rec["task_type"], "success": rec["success"]})
            if rec.get("explanation"):
                st.subheader("代码解释")
                st.markdown(rec["explanation"])
            for att in rec.get("attempts", []):
                if att.get("exec"):
                    _show_exec(att["code"], att["exec"],
                               att["exec"].get("figures", []))
            if rec.get("figure_paths"):
                st.subheader("图表")
                for fp in rec["figure_paths"]:
                    if os.path.exists(fp):
                        st.image(fp, use_container_width=True)

# ================================================================ 金融文档问答
elif tab == "金融文档问答":
    st.subheader("📄 金融文档问答")
    st.write("上传金融 PDF（年报/财务报告），系统自动解析 → 切分 → 索引 → 检索 → 证据定位 → LLM 回答。")
    col1, col2 = st.columns(2)
    with col1:
        pdf = st.file_uploader("上传金融 PDF", type=["pdf"])
    with col2:
        builtin = None
        if (config.PDF_DIR / "示例财务报告.pdf").exists():
            builtin = st.checkbox("使用内置示例年报", value=(pdf is None))
    qs = st.text_area("问题", height=80, placeholder="例如：公司2023年的营业收入是多少？毛利率是多少？")
    if st.button("回答", key="run_docqa", type="primary"):
        path = None
        if builtin:
            path = str(config.PDF_DIR / "示例财务报告.pdf")
        elif pdf is not None:
            path = _save_upload(pdf)
        if path is None:
            st.warning("请上传 PDF 或勾选内置示例年报")
        elif not qs.strip():
            st.warning("请输入问题")
        else:
            agent = FinancialDocQA(model=model, temperature=temperature,
                                   max_tokens=int(max_tokens), task_prompt=use_task_prompt,
                                   allow_code=allow_code)
            with st.spinner("解析 PDF、检索证据并生成回答……"):
                agent.load(path)
                result = agent.answer(qs.strip())
            st.subheader("回答")
            st.write(result["answer"])
            if result.get("evidence"):
                st.subheader(f"检索到的证据（Top {len(result['evidence'])}）")
                for e in result["evidence"]:
                    st.markdown(f"**第 {e['page']} 页** · {e['type']} · 相似度 {e['score']:.3f}")
                    st.code(e["text"], language=None)

# ================================================================ 金融数据分析
elif tab == "金融数据分析":
    st.subheader("📊 金融数据分析")
    st.write("读取 CSV/Excel，根据分析目标自动完成金融指标计算、数据处理、统计分析、可视化与结果解释。")
    col1, col2 = st.columns(2)
    with col1:
        up = st.file_uploader("上传数据文件（CSV/Excel）", type=["csv", "xlsx", "xls"])
    with col2:
        demo = st.checkbox("使用内置示例财务数据（三年利润表/资产负债表）", value=(up is None))
    q = st.text_area("分析目标", height=80,
                     placeholder="例如：计算每年的营业收入增长率和净利润增长率并绘制折线图，分析趋势")
    if st.button("开始分析", key="run_da", type="primary"):
        path = None
        if demo:
            path = str(config.SAMPLE_DATA_DIR / "示例公司财务数据.xlsx")
        elif up is not None:
            path = _save_upload(up)
        if path is None:
            st.warning("请上传数据或使用内置示例")
        elif not q.strip():
            st.warning("请输入分析目标")
        else:
            agent = FinancialDataAnalysis(model=model, temperature=temperature,
                                          max_tokens=int(max_tokens),
                                          task_prompt=use_task_prompt, allow_code=allow_code)
            with st.spinner("生成并执行分析代码……"):
                rec = agent.run(q.strip(), path)
            st.success("分析完成" if rec["success"] else "执行失败")
            if rec.get("code"):
                _show_exec(rec["code"], rec.get("exec"), rec.get("figures"))
            if rec.get("interpretation"):
                st.subheader("结果解释")
                st.markdown(rec["interpretation"])

# ================================================================ 数学建模
else:
    st.subheader("🧮 数学建模")
    st.write("从问题理解、变量与假设、模型选择、建模求解、代码执行到结果评价与结论解释的完整流程。")
    col1, col2 = st.columns(2)
    with col1:
        up = st.file_uploader("上传数据文件（可选）", type=["csv", "xlsx", "xls"])
    with col2:
        demo = st.checkbox("使用内置示例建模数据（企业财务指标综合评价）", value=(up is None))
    prob = st.text_area("建模问题", height=120,
                        placeholder="例如：基于企业多项财务指标，对企业进行信用风险综合评价与排序")
    if st.button("开始建模", key="run_mm", type="primary"):
        path = None
        if demo:
            path = str(config.SAMPLE_DATA_DIR / "企业信用评价示例数据.csv")
        elif up is not None:
            path = _save_upload(up)
        if not prob.strip():
            st.warning("请输入建模问题")
        else:
            agent = MathModeling(model=model, temperature=temperature,
                                 max_tokens=int(max_tokens), task_prompt=use_task_prompt,
                                 allow_code=allow_code)
            with st.spinner("数学建模进行中……"):
                rec = agent.run(prob.strip(), data_path=path)
            st.success("建模完成" if rec["success"] else "执行失败")
            if rec.get("design"):
                with st.expander("📝 问题理解 / 变量与假设 / 模型选择 / 求解方案", expanded=True):
                    st.markdown(rec["design"])
            if rec.get("code"):
                _show_exec(rec["code"], rec.get("exec"), rec.get("figures"))
            if rec.get("evaluation"):
                st.subheader("模型评价与结论")
                st.markdown(rec["evaluation"])
