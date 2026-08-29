"""Financial Agent 的金融数值推理模块（用于 FinQA / FinanceMath 主对比与消融）。

流程：问题与表格/文本输入 → （可选）生成 Python 程序 → 沙箱执行 →
失败时根据错误反馈修复 → 输出最终数值答案。
消融 w/o Code Execution 时仅由 LLM 直接推理。
"""
import re

import config
import executor
import llm as llm_module
from . import prompts
from .extract import extract_python_code


def format_context(question, table=None, context=None, options=None):
    """统一输入格式：问题 + 可选表格 + 可选上下文。"""
    parts = [f"问题：{question}"]
    if context and context.strip():
        parts.append(f"背景文本：\n{context.strip()}")
    if table is not None and str(table).strip():
        parts.append(f"表格：\n{table}")
    if options:
        parts.append(f"选项：{options}")
    return "\n\n".join(parts)


class FinancialNumericAgent:
    """Financial Agent 的金融数值问答模块。"""

    def __init__(self, model=None, temperature=None, max_tokens=None,
                 task_prompt=True, allow_code=True, max_fix_attempts=2):
        self.model = model or config.DEFAULT_MODEL
        self.temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature
        self.max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
        self.task_prompt = task_prompt
        self.allow_code = allow_code
        self.max_fix_attempts = max_fix_attempts

    # ---------------------------------------------------------------- 代码生成
    def _gen_program(self, task_text, fix_error=None, label="fa_gen"):
        system = prompts.system_prompt("benchmark", self.task_prompt)
        user = task_text + "\n\n" + prompts.BENCHMARK_CODE_GENERATION_PROMPT
        if fix_error:
            user += f"\n\n上次运行错误：{fix_error}\n请修正后重新输出完整代码。"
        resp = llm_module.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=max(self.max_tokens, config.CODE_GEN_MAX_TOKENS), label=label,
        )
        return extract_python_code(resp["text"])

    # ---------------------------------------------------------------- 直接推理（无代码执行）
    def _reason_direct(self, task_text):
        system = prompts.system_prompt("benchmark", self.task_prompt)
        user = task_text + "\n\n" + prompts.REASON_ONLY_PROMPT
        resp = llm_module.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=self.max_tokens, label="fa_reason",
        )
        return resp["text"]

    # ---------------------------------------------------------------- 答案提取
    @staticmethod
    def extract_answer(text):
        """从输出文本中提取最终数值答案。"""
        if not text:
            return None
        # 优先匹配 "最终答案：X" / "answer: X" / "答案是 X"
        m = re.search(r"(?:最终答案|答案是|answer|Answer)\s*[:：]\s*([-+]?\d[\d,\.]*)", text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except Exception:
                pass
        # 提取最后一个数字（考虑百分号：5.2% → 0.052 会误判，这里仅当无百分比时才取最后数字）
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", text.replace(",", ""))
        if not nums:
            return None
        try:
            return float(nums[-1])
        except Exception:
            return None

    # ---------------------------------------------------------------- 主流程
    def run(self, question, table=None, context=None, options=None):
        task_text = format_context(question, table, context, options)
        records = {"question": question, "code": None, "exec": None,
                   "reasoning": None, "success": False}

        if not self.allow_code:
            text = self._reason_direct(task_text)
            records["reasoning"] = text
            records["answer"] = self.extract_answer(text)
            records["reason_only"] = True
            records["success"] = records["answer"] is not None
            return records

        code = self._gen_program(task_text, label="fa_gen")
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
            code = self._gen_program(task_text, fix_error=err, label="fa_fix")
            records["code"] = code

        records["exec"] = last
        stdout = (last or {}).get("stdout", "") or ""
        records["answer"] = self.extract_answer(stdout)
        records["success"] = bool(last and last["success"])
        return records
