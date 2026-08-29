"""金融文档问答：PDF 解析 → 切分 → 索引 → 检索 → 证据定位 → LLM 回答。"""
import os
import re

import config
import llm as llm_module
from . import prompts


def _normalize_table(table):
    """将 pdfplumber 提取的表格转为文本表示。"""
    rows = []
    for row in table.extract():
        cells = [(c or "").strip().replace("\n", " ") for c in row]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


class FinancialDocQA:
    def __init__(self, model=None, temperature=None, max_tokens=None,
                 task_prompt=True, allow_code=True, top_k=6, chunk_size=900, overlap=120):
        self.model = model or config.DEFAULT_MODEL
        self.temperature = config.DEFAULT_TEMPERATURE if temperature is None else temperature
        self.max_tokens = max_tokens or config.DEFAULT_MAX_TOKENS
        self.task_prompt = task_prompt
        self.allow_code = allow_code
        self.top_k = top_k
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks = []
        self._vec = None
        self._tfidf = None

    # ---------------------------------------------------------------- 解析
    def parse_pdf(self, path):
        import pdfplumber
        pages = []
        with pdfplumber.open(path) as pdf:
            for pi, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                tables = []
                for tb in page.extract_tables():
                    rows = []
                    for row in tb:
                        cells = [(c or "").strip().replace("\n", " ") for c in row]
                        rows.append("| " + " | ".join(cells) + " |")
                    if rows:
                        tables.append("\n".join(rows))
                pages.append({"page": pi, "text": text, "tables": tables,
                              "n_chars": len(text)})
        return pages

    # ---------------------------------------------------------------- 切分
    def chunk_pages(self, pages):
        chunks = []
        for pg in pages:
            text = pg["text"]
            i = 0
            while i < len(text):
                piece = text[i:i + self.chunk_size]
                chunks.append({
                    "text": piece.strip(),
                    "page": pg["page"],
                    "type": "text",
                })
                i += self.chunk_size - self.overlap
            for t_idx, tb in enumerate(pg["tables"]):
                chunks.append({
                    "text": tb,
                    "page": pg["page"],
                    "type": "table",
                })
        return chunks

    # ---------------------------------------------------------------- 索引
    @staticmethod
    def _seg(text):
        """中文分词 + 英文数字保留，供 TF-IDF 检索使用。"""
        import jieba
        toks = [t.strip() for t in jieba.cut(text) if t.strip()]
        return " ".join(toks)

    def build_index(self, chunks=None):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.chunks = chunks or self.chunks
        if not self.chunks:
            raise ValueError("没有可索引的文档内容")
        texts = [self._seg(c["text"]) for c in self.chunks]
        self._tfidf = TfidfVectorizer(
            lowercase=True, token_pattern=r"(?u)\b\w+\b",
            ngram_range=(1, 2), max_features=30000)
        self._vec = self._tfidf.fit_transform(texts)
        return self._vec

    # ---------------------------------------------------------------- 检索
    def retrieve(self, question, top_k=None):
        from sklearn.metrics.pairwise import cosine_similarity
        top_k = top_k or self.top_k
        q_vec = self._tfidf.transform([self._seg(question)])
        sims = cosine_similarity(q_vec, self._vec)[0]
        order = sims.argsort()[::-1]
        results = []
        for idx in order[:top_k]:
            results.append({
                "chunk": self.chunks[idx],
                "score": float(sims[idx]),
            })
        return results

    # ---------------------------------------------------------------- 问答
    def load(self, path):
        pages = self.parse_pdf(path)
        chunks = self.chunk_pages(pages)
        self.build_index(chunks)
        return {"pages": pages, "n_chunks": len(chunks)}

    def answer(self, question, include_evidence=True):
        evid = self.retrieve(question)
        if not evid:
            return {"question": question, "answer": "未检索到相关证据。", "evidence": [],
                    "success": True}
        evidence_text = "\n\n".join(
            f"[第{e['chunk']['page']}页|{e['chunk']['type']}]\n{e['chunk']['text']}"
            for e in evid)
        system = prompts.system_prompt("doc_qa", self.task_prompt)
        user = (f"问题：{question}\n\n【证据】\n{evidence_text}\n\n"
                f"请根据以上证据回答问题，并标注来源页码。")
        resp = llm_module.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            model=self.model, temperature=self.temperature,
            max_tokens=self.max_tokens, label="doc_qa",
        )
        result = {
            "question": question,
            "answer": resp["text"],
            "success": True,
        }
        if include_evidence:
            result["evidence"] = [
                {"page": e["chunk"]["page"], "type": e["chunk"]["type"],
                 "text": e["chunk"]["text"][:400], "score": e["score"]}
                for e in evid]
        return result
