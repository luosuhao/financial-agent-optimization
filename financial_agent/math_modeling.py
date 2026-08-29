"""数学建模：问题理解 → 变量/假设 → 模型选择 → 建模求解 → 代码生成执行
→ 结果评价 → 可视化与结论解释。"""
import config
import executor
import llm as llm_module
from . import prompts
from .extract import extract_python_code

MODELING_STEPS = [
    "1. 问题理解与目标分析",
    "2. 变量定义与必要假设",
    "3. 数学模型或方法选择",
    "4. 模型建立与求解方案",
    "5. Python 代码生成与执行",
    "6. 模型结果评价",
    "7. 可视化与结论解释",
]


class MathModeling:
    def __init__(self, model=None, temperature=None, max_tokens=None,
                 task_prompt=True, allow_code=True, max_fix_attempts=2):
        self.model = model or config.DEFAULT_MODEL
        self.temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature
        self.max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
        self.task_prompt = task_prompt
        self.allow_code = allow_code
        self.max_fix_attempts = max_fix_attempts

    # ---------------------------------------------------------------- 建模设计
    def design(self, problem, data_info=""):
        system = prompts.system_prompt("math_modeling", self.task_prompt)
        user = (f"建模问题：{problem}\n\n{data_info}\n"
                f"请完成建模设计的第1~4步（问题理解与目标、变量与假设、模型选择、模型建立与求解方案）。"
                f"用中文清晰列出。")
        resp = llm_module.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=self.max_tokens, label="modeling_design",
        )
        return resp["text"]

    # ---------------------------------------------------------------- 代码生成
    def gen_code(self, problem, design, data_info="", fix_error=None):
        system = prompts.system_prompt("math_modeling", self.task_prompt)
        user = (f"建模问题：{problem}\n{data_info}\n\n建模设计：\n{design}\n\n"
                f"请生成完整 Python 代码实现第5步（模型建立与求解）。要求："
                f"数据用 pandas 读取；结果用 print 输出关键评价指标；"
                f"绘图用 matplotlib 并 plt.savefig('figure.png')。只输出代码块。")
        if fix_error:
            user += f"\n\n上次运行错误：{fix_error}\n请修正后输出完整代码。"
        resp = llm_module.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=max(self.max_tokens, config.CODE_GEN_MAX_TOKENS), label="modeling_gen",
        )
        return extract_python_code(resp["text"])

    # ---------------------------------------------------------------- 结果评价与结论
    def evaluate(self, problem, design, stdout, figures):
        system = prompts.system_prompt("math_modeling", self.task_prompt)
        user = (f"建模问题：{problem}\n建模设计：{design}\n\n程序运行输出：\n{stdout[:3000]}\n\n"
                f"请完成第6~7步：评价模型结果（给出评价指标及数值），并给出可视化说明与最终结论。用中文。")
        resp = llm_module.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=self.max_tokens, label="modeling_eval",
        )
        return resp["text"]

    # ---------------------------------------------------------------- 主流程
    def run(self, problem, data_path=None):
        data_info = ""
        if data_path:
            import pandas as pd
            try:
                df = pd.read_csv(data_path) if not str(data_path).endswith((".xlsx", ".xls")) \
                    else pd.read_excel(data_path)
                data_info = (f"数据文件：{data_path}\n列名：{', '.join(str(c) for c in df.columns)}\n"
                             f"前5行：\n{df.head(5).to_string()}\n")
            except Exception as e:
                data_info = f"数据加载失败：{e}\n"

        records = {"problem": problem, "data_path": data_path, "design": None,
                   "code": None, "exec": None, "evaluation": None,
                   "figures": [], "success": False, "steps": []}

        design = self.design(problem, data_info)
        records["design"] = design

        if not self.allow_code:
            system = prompts.system_prompt("math_modeling", self.task_prompt)
            user = (f"建模问题：{problem}\n{data_info}\n\n建模设计：\n{design}\n\n"
                    f"请在不编写代码的前提下，手工完成模型求解过程，给出主要计算结果、评价指标和结论。用中文。")
            resp = llm_module.chat(
                [{"role": "system", "content": system}, {"role": "user", "content": user}],
                model=self.model, temperature=self.temperature,
                max_tokens=self.max_tokens, label="modeling_reason",
            )
            records["evaluation"] = resp["text"]
            records["reason_only"] = True
            records["success"] = True
            return records

        code = self.gen_code(problem, design, data_info)
        records["code"] = code
        last = None
        for _ in range(self.max_fix_attempts + 1):
            last = executor.execute_code(code, timeout=config.EXEC_TIMEOUT,
                                         workdir=str(config.BASE_DIR))
            if last["success"]:
                break
            err = f"{last.get('error_type')}: {last.get('error_msg')}"
            if "TimeoutError" in err:
                break
            code = self.gen_code(problem, design, data_info, fix_error=err)
            records["code"] = code

        records["exec"] = last
        if last.get("figures"):
            records["figures"] = last["figures"]
        if last["success"]:
            records["evaluation"] = self.evaluate(
                problem, design, last.get("stdout", ""), last.get("figures", []))
            records["success"] = True
        return records
