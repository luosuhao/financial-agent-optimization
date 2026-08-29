"""全局配置：读取 .env 中的 API Key 与模型参数。"""
import os
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent


def _load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv(BASE_DIR / ".env")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# 主实验公平性设置：MoCA-Agent 与 Financial Agent 使用相同模型参数
DEFAULT_TEMPERATURE = float(os.environ.get("DEFAULT_TEMPERATURE", "0.0"))
DEFAULT_MAX_TOKENS = int(os.environ.get("DEFAULT_MAX_TOKENS", "4096"))
# 代码生成类调用使用更大的输出上限（避免长代码被截断）
CODE_GEN_MAX_TOKENS = 8192

# 代码执行开关（消融实验 w/o Code Execution 时置 False）
DEFAULT_ALLOW_CODE = True
# 任务专用 Prompt 开关（消融实验 w/o Task-specific Prompt 时置 False）
DEFAULT_TASK_PROMPT = True

DATA_DIR = BASE_DIR / "data"
FINQA_DIR = DATA_DIR / "finqa"
FINANCEMATH_DIR = DATA_DIR / "financemath"
SAMPLE_DATA_DIR = DATA_DIR / "sample_data"
PDF_DIR = DATA_DIR / "pdfs"
RESULTS_DIR = BASE_DIR / "results"
REPORT_DIR = BASE_DIR / "report"

for _d in (RESULTS_DIR, REPORT_DIR, SAMPLE_DATA_DIR, PDF_DIR):
    _d.mkdir(parents=True, exist_ok=True)

EXEC_TIMEOUT = 15  # 代码执行沙箱超时（秒）

# 固定测试题规模
MAIN_N_FINQA = 20
MAIN_N_FINANCEMATH = 20
ABLATION_N_TOTAL = 24
