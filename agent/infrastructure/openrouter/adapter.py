"""OpenRouter ACL — wraps the ``openai`` SDK with an OpenRouter base URL.

See ADR-0005 and ``docs/ddd/11-anti-corruption-layers.md``.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from agent.domain.errors import LlmUnavailable
from agent.domain.ports import LlmCompletionPort

logger = logging.getLogger(__name__)


DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-3.5-turbo"


class OpenRouterAdapter(LlmCompletionPort):
    """OpenAI-compatible client pointed at OpenRouter.

    All exceptions are translated to :class:`LlmUnavailable` so the upstream
    :class:`IntentExtractionService` can fall through to the regex path.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self._base_url = base_url
        self._model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
        self._client: Any = None  # lazy

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise LlmUnavailable("OPENROUTER_API_KEY is not set")
        try:
            import openai
        except ImportError as exc:
            raise LlmUnavailable("openai SDK not installed") from exc
        self._client = openai.OpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    def complete(self, prompt: str, *, max_tokens: int = 50, temperature: float = 0.1) -> str:
        try:
            client = self._ensure_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            choice = response.choices[0]
            content = (choice.message.content or "").strip()
            if not content:
                raise LlmUnavailable("OpenRouter returned an empty completion")
            return content
        except LlmUnavailable:
            raise
        except Exception as exc:
            logger.warning("openrouter.error model=%s err=%s", self._model, exc)
            raise LlmUnavailable(f"OpenRouter error: {exc}") from exc
