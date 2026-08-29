"""LLM/임베딩 프로바이더.

- Chat: DeepSeek (OpenAI 호환, base_url=api.deepseek.com, model=deepseek-chat)
- Embedding: DeepSeek는 임베딩 API를 제공하지 않으므로 로컬 해시 기반
  임베딩으로 폴백한다. 외부 호출 없이 결정적 벡터를 만들어 pgvector에
  적재할 수 있게 하며, 실제 임베딩 모델 도입 시 embed_texts만 교체하면 된다.

키(DEEPSEEK_API_KEY)가 없으면 has_llm()이 False가 되어, 호출부가
규칙기반 폴백 경로로 분기할 수 있다.
"""
from __future__ import annotations

import hashlib
import math
import re

from app.core.config import settings


def has_llm() -> bool:
    """실제 LLM 호출이 가능한지(키 존재 여부)."""
    return bool(settings.deepseek_api_key)


# ---------------- Embeddings (로컬 해시 기반 폴백) ----------------
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def embed_text(text: str) -> list[float]:
    """결정적 해시 기반 bag-of-words 임베딩(L2 정규화).

    외부 API 없이 동작한다. 의미 유사도 성능은 실제 임베딩 모델보다
    낮지만, 파이프라인/인덱싱 검증과 폴백 매칭에는 충분하다.
    """
    dim = settings.embedding_dim
    vec = [0.0] * dim
    for tok in _tokenize(text):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [embed_text(t) for t in texts]


# ---------------- Chat (DeepSeek) ----------------
def chat_complete(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    """DeepSeek chat 완성. 키가 없으면 LLMConfigError 대신 호출부가
    has_llm()으로 사전 분기하는 것을 권장한다."""
    if not settings.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 미설정: 규칙기반 폴백 경로를 사용하세요.")

    from openai import OpenAI

    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.llm_base_url,
    )
    resp = client.chat.completions.create(
        model=settings.llm_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content or ""
