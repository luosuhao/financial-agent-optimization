# 金融数据分析（独立可移植包）

读取 CSV/Excel 金融数据，根据自然语言分析目标自动完成：
金融指标计算、数据处理、统计分析、可视化与结果解释。

本文件夹完全自包含，**可单独拷贝到其他机器运行**，不依赖主系统。

## 独立运行（拷贝到新机器后）

```bash
# 1. 安装依赖
pip install -r data_analysis/requirements.txt

# 2. 配置 DeepSeek API Key（复制示例并填写）
cp .env.example .env      # Windows: copy .env.example .env

# 3. 运行（在包含 data_analysis 的父目录下）
python -m data_analysis.run_analysis --data 数据文件.xlsx --question "计算2022和2023年的营业收入增长率、毛利率并绘图"
```

## 命令行参数

| 参数 | 说明 |
|---|---|
| `--data` | 数据文件路径（CSV/Excel，必填） |
| `--question` | 分析目标（必填） |
| `--no-task-prompt` | 关闭任务专用 Prompt（消融实验用） |
| `--no-code` | 关闭代码执行，仅 LLM 直接推理（消融实验用） |
| `--model` | 覆盖模型（默认 deepseek-chat） |
| `--temperature` | 覆盖 temperature（默认 0.0） |
| `--max-tokens` | 覆盖最大输出 Token |
| `--out-dir` | 图表输出目录（默认 data_analysis/output） |

## 示例

```bash
python -m data_analysis.run_analysis \
  --data data/sample_data/示例公司财务数据.xlsx \
  --question "计算2022和2023年的营业收入增长率、净利润增长率、毛利率并绘图"
```

输出内容：生成的 Python 代码、执行日志、图表（保存到 output/）、结果解释、Token 用量。

## 作为 Python 包使用

```python
from data_analysis import FinancialDataAnalysis

agent = FinancialDataAnalysis()          # 或 task_prompt=False / allow_code=False
result = agent.run("计算毛利率趋势", "数据.xlsx")
print(result["interpretation"])
```

## 文件说明

| 文件 | 说明 |
|---|---|
| `analyzer.py` | 核心类 `FinancialDataAnalysis` |
| `config.py` | 配置（读取 .env：本文件夹 → 父目录） |
| `llm.py` | DeepSeek LLM 封装（记录 Token） |
| `executor.py` / `exec_runner.py` | 安全代码执行沙箱 |
| `prompts.py` | 任务专用 / 通用 Prompt |
| `extract.py` | Python 代码提取 |
| `run_analysis.py` | 命令行入口 |
