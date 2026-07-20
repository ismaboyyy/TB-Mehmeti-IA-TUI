"""Client LLM Ollama (LangChain). Le modèle est configurable via .env
pour pouvoir comparer llama3.2:3b, qwen2.5:7b, mistral:7b."""
from __future__ import annotations

from functools import lru_cache

from langchain_ollama import ChatOllama

from app.core.config import settings


@lru_cache
def get_llm(model: str | None = None, temperature: float = 0.1) -> ChatOllama:
    return ChatOllama(
        model=model or settings.ollama_llm_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
    )
