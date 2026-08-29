"""MoCA-Agent (MoCA-Fin) 复现实现。

流程（参考论文 Section 3）：
  Claim Catalog Builder → Specialist Trader Market(Extractor/Formula/Accountant/Skeptic)
  → Claim Market Clearing → Synthesizer(Python 程序) → 沙箱执行
  → Code-Aware Verifier → (必要时) Market-Aware Repair 一次。
"""
import re
import sys
import time

import config
import executor
import llm as llm_module

sys.path.insert(0, str(config.BASE_DIR))
from financial_agent.extract import extract_python_code

M_MAX = 10
EPS = 1e-6
PI_UP, PI_DOWN = 0.62, 0.38
WEIGHTS = {"extractor": 1.00, "formula": 1.00, "accountant": 1.10, "skeptic": 0.95}
ROLES = ["extractor", "formula", "accountant", "skeptic"]
PHI_THRESHOLD = 2.20
KINDS = ["fact", "formula", "unit", "sign", "direction", "other"]
TYPES = ["percentage-change", "ratio", "sum", "difference", "average", "comparison", "other"]

CLAIM_PROMPT = """You are building a typed claim catalog for a financial/tabular reasoning question.
Question: {question}
{table_block}
{context_block}
Decompose the question into at most {m_max} atomic, tradable claims needed to answer it.
Each claim has: kind ∈ {kinds}, summary (one-line), value (number/expression/unit), evidence (short quote from text/table).
Also classify the overall problem type τ ∈ {types}.
Respond ONLY with JSON:
{{
  "problem_type": "<one of {types}>",
  "claims": [
    {{"id": 1, "kind": "fact", "summary": "...", "value": "...", "evidence": "..."}}
  ]
}}"""

TRADER_PROMPT = """You are the {role} specialist trader in a claim market for financial reasoning.
You review the claims below and place BUY or SELL orders based on your role expertise:
- extractor: grounds factual cells against the table/context.
- formula: validates that formulas obey the requested operation.
- accountant: cross-checks units and accounting conventions (revenue, expense, net).
- skeptic: actively sells under-evidenced claims.
For each claim provide: side ("buy"/"sell"), size (integer 1..5), price (0.01..0.99, confidence of the order),
and a short rationale. Respond ONLY with JSON:
{{"orders": [
  {{"id": 1, "side": "buy", "size": 3, "price": 0.85, "rationale": "..."}}
]}}

Question: {question}
{table_block}
{context_block}
Claims:
{claims_json}"""

SYNTHESIZER_PROMPT = """You are a code synthesizer. Write a Python program to answer the financial question.
You may ONLY rely on claims whose market status is "accepted" or "uncertain" (NOT rejected).
Market status of claims:
{status_json}
Use numpy/pandas. The program must print the final numeric answer via print(ans) where ans is a single float.
Output ONLY the Python code block."""

REPAIR_PROMPT = """The synthesized program failed or was rejected. Fix the program.
Previous code:
```python
{code}
```
Problem details:
Question: {question}
{table_block}
{context_block}
Market status of claims:
{status_json}
Error/feedback:
{feedback}
Output ONLY the corrected Python code block. The program must print the final numeric answer via print(ans)."""


class MoCAFinaAgent:
    """MoCA-Agent / MoCA-Fin 复现。"""

    def __init__(self, model=None, temperature=None, max_tokens=None,
                 allow_repair=True, m_max=M_MAX):
        self.model = model or config.DEFAULT_MODEL
        self.temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature
        self.max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
        self.allow_repair = allow_repair
        self.m_max = m_max

    # ---------------------------------------------------------------- 输入格式
    @staticmethod
    def _format(q, table=None, context=None):
        tb = f"Table:\n{table}" if table is not None and str(table).strip() else ""
        cb = f"Context:\n{context}" if context and str(context).strip() else ""
        return tb, cb

    # ---------------------------------------------------------------- Step1: Claim Catalog
    def build_claims(self, question, table=None, context=None):
        tb, cb = self._format(question, table, context)
        user = CLAIM_PROMPT.format(
            question=question, table_block=tb, context_block=cb,
            m_max=self.m_max, kinds=KINDS, types=TYPES)
        resp = llm_module.chat(
            [{"role": "system", "content": "You are an expert financial reasoning agent. Respond in JSON only."},
             {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=self.max_tokens, json_mode=True, label="moca_claims",
        )
        data = llm_module.extract_json(resp["text"]) or {}
        claims = data.get("claims", [])
        if isinstance(claims, dict):
            claims = list(claims.values())
        claims = [c for c in claims if isinstance(c, dict) and "id" in c][:self.m_max]
        problem_type = data.get("problem_type")
        if problem_type not in TYPES:
            problem_type = "other"
        return claims, problem_type

    # ---------------------------------------------------------------- Step2: Trader Market
    def trade(self, role, question, table=None, context=None, claims=None):
        tb, cb = self._format(question, table, context)
        claims_json = "\n".join(
            f"id={c['id']}, kind={c.get('kind')}, summary={c.get('summary')}, "
            f"value={c.get('value')}, evidence={c.get('evidence')}"
            for c in (claims or []))
        user = TRADER_PROMPT.format(
            role=role, question=question, table_block=tb, context_block=cb,
            claims_json=claims_json)
        resp = llm_module.chat(
            [{"role": "system", "content": "You are a financial claim-market trader. Respond in JSON only."},
             {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=self.max_tokens, json_mode=True, label=f"moca_trader_{role}",
        )
        data = llm_module.extract_json(resp["text"]) or {}
        orders = data.get("orders", [])
        if isinstance(orders, dict):
            orders = list(orders.values())
        return orders

    # ---------------------------------------------------------------- Step3: Market Clearing
    @staticmethod
    def clear(claims, order_books):
        """order_books: dict role -> list of orders."""
        buy = {}
        sell = {}
        for role, orders in order_books.items():
            w = WEIGHTS.get(role, 1.0)
            for o in orders:
                if not isinstance(o, dict) or "id" not in o:
                    continue
                cid = int(o["id"])
                n = int(o.get("size", 1))
                p = float(o.get("price", 0.5))
                p = max(0.01, min(0.99, p))
                if o.get("side") == "sell":
                    sell[cid] = sell.get(cid, 0.0) + w * n * p
                else:
                    buy[cid] = buy.get(cid, 0.0) + w * n * p
        statuses = {}
        for c in claims:
            cid = int(c["id"])
            B = buy.get(cid, 0.0)
            S = sell.get(cid, 0.0)
            pi = B / (B + S + EPS)
            gamma = abs(B - S) / (B + S + EPS)
            if pi >= PI_UP:
                status = "accepted"
            elif pi <= PI_DOWN:
                status = "rejected"
            else:
                status = "uncertain"
            statuses[cid] = {"price": round(pi, 4), "confidence": round(gamma, 4), "status": status}
        return statuses

    # ---------------------------------------------------------------- Step4: Synthesizer
    def synthesize(self, question, table=None, context=None, claims=None, statuses=None):
        tb, cb = self._format(question, table, context)
        status_json = "\n".join(
            f"id={c['id']}, kind={c.get('kind')}, value={c.get('value')}, status={statuses.get(int(c['id']), {}).get('status')}"
            for c in (claims or []))
        user = SYNTHESIZER_PROMPT.format(
            question=question, table_block=tb, context_block=cb, status_json=status_json)
        resp = llm_module.chat(
            [{"role": "system", "content": "You are a Python code synthesizer for financial reasoning."},
             {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=max(self.max_tokens, config.CODE_GEN_MAX_TOKENS), label="moca_synth",
        )
        return extract_python_code(resp["text"])

    # ---------------------------------------------------------------- Step5: Verifier
    def verify(self, code, exec_result, claims, statuses, problem_type, used_claims):
        score = 1.00 + 0.20 * min(len([c for c in used_claims
                                       if statuses.get(int(c), {}).get("status") == "accepted"]), 4)
        gamma_vals = [statuses.get(int(c), {}).get("confidence", 0.0) for c in used_claims]
        score += 0.40 * (sum(gamma_vals) / len(gamma_vals) if gamma_vals else 0.0)

        violations = 0
        msgs = []
        if not exec_result.get("success"):
            violations += 1
            msgs.append(f"程序执行失败: {exec_result.get('error_type')}")
        op_types = {"percentage-change", "ratio", "sum", "difference", "average", "comparison"}
        if problem_type in op_types:
            n_facts = sum(1 for c in claims if c["id"] in used_claims
                          and c.get("kind") == "fact")
            if n_facts < 2:
                violations += 1
                msgs.append(f"fact 证据不足 (需要≥2, 实际{n_facts})")
        # 引用了被拒绝的 claim
        rejected_used = [c for c in used_claims
                         if statuses.get(int(c), {}).get("status") == "rejected"]
        if rejected_used:
            violations += 1
            msgs.append(f"引用了被市场拒绝的 claim: {rejected_used}")
        # 答案一致性：是否输出数值
        if not re.search(r"[-+]?\d+\.?\d*", exec_result.get("stdout", "")):
            violations += 1
            msgs.append("输出中没有数值答案")

        final_score = score - 0.45 * violations
        accepted = final_score >= PHI_THRESHOLD
        return {"score": round(final_score, 3), "accepted": accepted,
                "violations": msgs, "n_used": len(used_claims)}

    def _used_claims_from_code(self, code, claims):
        """从代码中判断使用了哪些 claim（按 id 关键词）。粗略匹配。"""
        used = set()
        for c in claims:
            for token in (str(c["id"]), str(c.get("value", ""))[:12]):
                if token and token in code:
                    used.add(int(c["id"]))
                    break
        return list(used)

    # ---------------------------------------------------------------- Repair
    def repair(self, question, table=None, context=None, claims=None,
               statuses=None, code=None, feedback=None):
        tb, cb = self._format(question, table, context)
        status_json = "\n".join(
            f"id={c['id']}, status={statuses.get(int(c['id']), {}).get('status')}"
            for c in (claims or []))
        user = REPAIR_PROMPT.format(
            code=code, question=question, table_block=tb, context_block=cb,
            status_json=status_json, feedback=feedback)
        resp = llm_module.chat(
            [{"role": "system", "content": "You are a Python code repair agent."},
             {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=max(self.max_tokens, config.CODE_GEN_MAX_TOKENS), label="moca_repair",
        )
        return extract_python_code(resp["text"])

    # ---------------------------------------------------------------- 主流程
    def run(self, question, table=None, context=None, options=None, verbose=False):
        t0 = time.time()
        trace = {"question": question, "claims": [], "orders": {}, "statuses": {},
                 "problem_type": None, "code": None, "exec": None,
                 "verify": None, "repaired": False, "answer": None}

        claims, problem_type = self.build_claims(question, table, context)
        trace["claims"] = claims
        trace["problem_type"] = problem_type

        order_books = {}
        for role in ROLES:
            orders = self.trade(role, question, table, context, claims)
            order_books[role] = orders
        trace["orders"] = order_books

        statuses = self.clear(claims, order_books)
        trace["statuses"] = statuses

        code = self.synthesize(question, table, context, claims, statuses)
        trace["code"] = code

        used = self._used_claims_from_code(code, claims)
        exec_result = executor.execute_code(code, timeout=config.EXEC_TIMEOUT,
                                            workdir=str(config.BASE_DIR))
        trace["exec"] = exec_result

        verdict = self.verify(code, exec_result, claims, statuses, problem_type, used)
        trace["verify"] = verdict

        # Market-Aware Repair（最多一次）
        if not verdict["accepted"] and self.allow_repair:
            feedback = "；".join(verdict["violations"])
            if exec_result.get("error_msg"):
                feedback += f"; {exec_result.get('error_type')}: {exec_result.get('error_msg')}"
            code2 = self.repair(question, table, context, claims, statuses, code, feedback)
            if code2 and code2 != code:
                trace["code"] = code2
                trace["repaired"] = True
                exec_result2 = executor.execute_code(code2, timeout=config.EXEC_TIMEOUT,
                                                     workdir=str(config.BASE_DIR))
                trace["exec"] = exec_result2
                used2 = self._used_claims_from_code(code2, claims)
                trace["verify"] = self.verify(code2, exec_result2, claims, statuses,
                                              problem_type, used2)

        stdout = trace["exec"].get("stdout", "") or ""
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?", stdout.replace(",", ""))
        if nums:
            trace["answer"] = float(nums[-1])
        trace["elapsed"] = round(time.time() - t0, 2)
        return trace
