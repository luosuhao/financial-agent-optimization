# 实验12：金融Agent构建及优化

本实验构建了一个面向金融任务的 **Financial Agent** 系统（含 Streamlit Web 界面），包含
**Coding Agent、金融文档问答、金融数据分析、数学建模** 四个功能模块；同时复现了
**MoCA-Agent（MoCA-Fin）** 作为对比基线，并完成主对比实验、消融实验、扩展能力实验和定性案例分析。

## 1. 项目结构

```
.
├── app.py                     # Streamlit Web 界面（streamlit run app.py）
├── config.py                  # 全局配置（读取 .env、模型参数、实验规模）
├── llm.py                     # DeepSeek LLM 统一封装（OpenAI 兼容，记录 Token 用量）
├── executor.py                # 安全代码执行器（subprocess 沙箱 + 超时）
├── exec_runner.py             # 沙箱子进程运行器
├── run_all.py                 # 一键运行全部实验
├── requirements.txt
├── .env                       # DeepSeek API Key（勿提交到公开仓库）
├── financial_agent/           # Financial Agent 模块（Coding/文档问答/数学建模/数值问答）
│   ├── coding_agent.py        #   Coding Agent
│   ├── doc_qa.py              #   金融文档问答（PDF 解析/检索/RAG）
│   ├── math_modeling.py       #   数学建模
│   ├── benchmark_agent.py     #   金融数值问答模块（主对比实验用）
│   ├── prompts.py             #   任务专用 Prompt 与通用 Prompt（消融开关）
│   └── extract.py             #   稳健的 Python 代码提取
├── data_analysis/             # 金融数据分析（独立可移植包）
│   ├── analyzer.py            #   核心类 FinancialDataAnalysis
│   ├── run_analysis.py        #   命令行入口（python -m data_analysis.run_analysis）
│   ├── config.py / llm.py     #   自带配置与 LLM 封装
│   ├── executor.py / exec_runner.py  # 自带代码执行沙箱
│   ├── prompts.py / extract.py
│   └── README.md              #   独立运行说明
├── moca_agent/
│   └── moca_agent.py          # MoCA-Agent 复现（Claim Market 全流程）
├── experiments/
│   ├── prepare_data.py        # 生成示例数据与示例年报 PDF
│   ├── benchmark.py           # 统一 Benchmark 输入接口（固定题集）
│   ├── eval.py                # 统一评价脚本（数值容差判定等）
│   ├── runner.py              # 统一 Agent 运行器
│   ├── run_main.py            # 主对比实验
│   ├── run_ablation.py        # 消融实验
│   ├── run_extension.py       # 扩展能力实验
│   ├── run_cases.py           # 定性案例分析
│   └── questions/             # 固定测试题集（main_set.json / ablation_set.json）
├── data/
│   ├── finqa/                 # FinQA dev.json
│   ├── financemath/           # FinanceMath test.json / validation.json
│   ├── sample_data/           # 示例 CSV / Excel 数据
│   └── pdfs/                  # 示例年报 PDF / 分红公告 PDF
├── results/                   # 实验结果（预测、指标、案例）
├── report/
│   ├── build_report.py        # 从 results/ 生成实验报告
│   └── 实验报告.md             # 实验报告
└── 2026-MoCA-Agent.pdf        # 参考论文
```

## 2. 环境准备

```bash
pip install -r requirements.txt
```

在 `.env` 中配置 DeepSeek API Key：

```
DEEPSEEK_API_KEY=sk-xxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

## 3. 快速开始

### 3.1 启动 Web 界面

```bash
streamlit run app.py
```

侧边栏可选择模型参数，并可开关两个消融设置（任务专用 Prompt、允许执行 Python 代码）。
四个功能模块：Coding Agent、金融文档问答、金融数据分析、数学建模。

### 3.2 金融数据分析命令行独立运行

金融数据分析已封装为独立可移植包 `data_analysis/`，可脱离 Web 界面单独运行（也支持拷贝到其他机器）：

```bash
python -m data_analysis.run_analysis \
  --data data/sample_data/示例公司财务数据.xlsx \
  --question "计算2022和2023年的营业收入增长率、毛利率并绘图"
```

### 3.3 生成示例数据与测试 PDF

```bash
python experiments/prepare_data.py
```

生成：
- `data/sample_data/示例公司财务数据.xlsx`（三年利润表/资产负债表）
- `data/sample_data/示例股票日收盘价.csv`
- `data/sample_data/投资组合日收益率.csv`
- `data/sample_data/企业信用评价示例数据.csv`
- `data/pdfs/示例财务报告.pdf`、`data/pdfs/示例分红公告.pdf`

### 3.3 运行实验

```bash
# 一键运行全部实验（主对比 + 消融 + 扩展 + 案例）
python run_all.py

# 或分步运行
python experiments/run_main.py              # 主对比实验
python experiments/run_ablation.py          # 消融实验
python experiments/run_extension.py         # 扩展能力实验
python experiments/run_cases.py             # 定性案例
```

支持断点续跑（自动加载已保存的部分预测结果）。冒烟测试：
```bash
python experiments/run_main.py --smoke 3    # 仅运行前 3 题
python experiments/run_ablation.py --smoke 3
```

### 3.4 生成实验报告

```bash
python report/build_report.py
```

## 4. 数据集

- **FinQA**：来自 `https://github.com/czyssrs/FinQA`（`dataset/dev.json`）
- **FinanceMath**：来自 `https://github.com/yale-nlp/FinanceMath`（`data/test.json`）

固定测试集保存于 `experiments/questions/`，题目编号与输入格式固定，保证对比公平。

## 5. 注意事项

- API Key 为敏感信息，`.env` 已被 `.gitignore` 排除，请勿提交到公开仓库。
- 主对比实验与消融实验会消耗 DeepSeek API 额度（预计千余次调用，成本几元到几十元）。

## 6.资源下载
完整打包程序（模型、依赖资源）不在Git仓库内，请通过网盘获取：
- 链接：https://pan.baidu.com/s/1VwpmevhETCtuGmz1oj1nkA
- 
- 提取码：`uren `
