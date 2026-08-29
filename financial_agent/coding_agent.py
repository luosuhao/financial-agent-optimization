"""Coding Agent：根据自然语言任务生成、理解、修改并执行 Python 代码。

支持基于执行错误反馈进行代码修改与重新执行（最多 MAX_FIX_ATTEMPTS 次）。
"""
import config
import executor
import llm as llm_module
from . import prompts
from .extract import extract_python_code

FIX_INSTRUCTION = (
    "上面的代码在运行中发生了错误。错误信息如下：\n"
    "{error}\n"
    "请分析错误原因并修改代码，输出一个完整可重新运行的 Python 代码块。"
)


class CodingAgent:
    def __init__(self, model=None, temperature=None, max_tokens=None,
                 task_prompt=True, allow_code=True, workdir=None,
                 max_fix_attempts=3):
        self.model = model or config.DEFAULT_MODEL
        self.temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature
        self.max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
        self.task_prompt = task_prompt
        self.allow_code = allow_code
        self.workdir = workdir or str(config.BASE_DIR)
        self.max_fix_attempts = max_fix_attempts

    # ---------------------------------------------------------------- 任务分类
    def classify(self, task):
        kw = {
            "generate": ["生成", "编写", "写一个", "实现", "计算", "calculate", "write", "generate", "create"],
            "explain": ["解释", "讲解", "说明", "讲解一下", "explain", "understand", "理解", "分析这段代码"],
            "fix": ["修复", "修改错误", "报错", "bug", "fix", "debug", "错误"],
            "modify": ["修改", "优化", "增加", "添加", "modify", "改进", "重构"],
        }
        low = task.lower()
        score = {}
        for k, words in kw.items():
            score[k] = sum(1 for w in words if w in low)
        best = max(score, key=score.get)
        return best if score[best] > 0 else "generate"

    # ---------------------------------------------------------------- 生成代码
    def _gen_code(self, task, existing_code=None, fix_error=None, label=""):
        system = prompts.system_prompt("coding", self.task_prompt)
        if fix_error:
            user = (
                f"任务：{task}\n\n"
                f"当前代码：\n```python\n{existing_code}\n```\n\n"
                + FIX_INSTRUCTION.format(error=fix_error)
            )
        else:
            user = f"任务：{task}\n请输出一个完整可运行的 Python 代码块。"
        resp = llm_module.chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=max(self.max_tokens, config.CODE_GEN_MAX_TOKENS), label="coding_gen",
        )
        return extract_python_code(resp["text"])

    # ---------------------------------------------------------------- 代码解释
    def _explain_code(self, task, code):
        system = prompts.system_prompt("coding_explain", self.task_prompt)
        resp = llm_module.chat(
            [{"role": "system", "content": system},
             {"role": "user", "content": f"请解释下面这段代码：\n```python\n{code}\n```\n任务背景：{task}"}],
            model=self.model, temperature=self.temperature,
            max_tokens=self.max_tokens, label="coding_explain",
        )
        return resp["text"]

    # ---------------------------------------------------------------- 主流程
    def run(self, task, existing_code=None, file_path=None):
        """执行 Coding Agent 全流程。"""
        records = {"task": task, "task_type": self.classify(task), "attempts": [], "figures": []}

        # 代码解释任务：不需要执行
        if self.classify(task) == "explain" and (existing_code or self.allow_code):
            if existing_code:
                explanation = self._explain_code(task, existing_code)
                records["task_type"] = "explain"
                records["code"] = existing_code
                records["explanation"] = explanation
                records["success"] = True
                return records

        code = existing_code
        if not code:
            code = self._gen_code(task, label="coding_gen")

        records["code"] = code
        records["attempts"].append({"attempt": 1, "code": code, "exec": None})

        # 代码执行（若开启）
        last_exec = None
        for attempt in range(1, self.max_fix_attempts + 1):
            if not self.allow_code:
                # 无代码执行：直接由 LLM 推理输出
                resp = llm_module.chat(
                    [{"role": "system", "content": prompts.system_prompt("coding", self.task_prompt)},
                     {"role": "user", "content": f"任务：{task}\n请直接给出最终结果，不要编写代码。"}],
                    model=self.model, temperature=self.temperature,
                    max_tokens=self.max_tokens, label="coding_reason",
                )
                last_exec = {"success": True, "stdout": resp["text"], "reason_only": True}
                records["attempts"][-1]["exec"] = last_exec
                break

            exec_result = executor.execute_code(
                code, timeout=config.EXEC_TIMEOUT, workdir=self.workdir)
            records["attempts"][-1]["exec"] = exec_result
            if exec_result.get("figures"):
                records["figures"].extend(exec_result["figures"])
            last_exec = exec_result

            if exec_result["success"]:
                break
            # 失败 → 根据错误反馈修改代码
            error_msg = f"{exec_result.get('error_type')}: {exec_result.get('error_msg')}"
            if "TimeoutError" in error_msg:
                break  # 超时不再修复
            fixed = self._gen_code(task, existing_code=code, fix_error=error_msg, label="coding_fix")
            if not fixed or fixed == code:
                break
            code = fixed
            records["code"] = code
            if attempt < self.max_fix_attempts:
                records["attempts"].append({"attempt": attempt + 1, "code": code, "exec": None})

        records["final_exec"] = last_exec
        records["success"] = bool(last_exec and last_exec.get("success"))
        records["figure_paths"] = records["figures"]
        return records
