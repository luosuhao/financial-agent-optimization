"""金融数字解析：从自然语言答案中提取所有数值，正确处理百分号与中文单位。"""
import re

UNIT_SCALES = {
    "十亿元": 1e9, "亿元": 1e8, "千万元": 1e7, "百万元": 1e6,
    "万元": 1e4, "千元": 1e3, "百元": 1e2, "元": 1.0, "美元": 1.0,
    "亿": 1e8, "万": 1e4,
}
# 按长度降序匹配，避免"亿元"被"元"截断
_UNIT_RE = "|".join(sorted(UNIT_SCALES.keys(), key=len, reverse=True))
_NUM_RE = re.compile(rf"([-+]?\d[\d,]*(?:\.\d+)?)\s*([%％]|{_UNIT_RE})?")


def parse_all_numbers(text):
    """返回文本中所有数值（含单位/百分号换算后的十进制值）。"""
    if not text:
        return []
    text = text.replace("，", ",")
    out = []
    for m in _NUM_RE.finditer(text):
        try:
            num = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        suffix = m.group(2)
        if not suffix:
            out.append(num)
        elif suffix in ("%", "％"):
            out.append(num / 100.0)
        else:
            out.append(num * UNIT_SCALES.get(suffix, 1.0))
    return out


def parse_financial_number(text):
    """兼容旧接口：返回文本中第一个数值（含单位/百分号换算）。"""
    nums = parse_all_numbers(text)
    return nums[0] if nums else None


def match_financial_answer(pred_text, gold, tol_rel=0.01, tol_abs=0.01):
    """判断模型答案文本中是否包含与标准答案一致的数值（含单位/百分号换算）。

    对文本中所有数值逐一与 gold 比较（可处理"2023年"等年份干扰）。
    """
    from experiments.eval import num_match
    if isinstance(gold, (int, float)):
        for num in parse_all_numbers(pred_text):
            if num_match(num, gold, tol_rel=tol_rel, tol_abs=tol_abs):
                return True
        return False
    # 文本型答案：宽松包含判断
    return bool(pred_text) and (gold in pred_text)
