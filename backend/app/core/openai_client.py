"""Azure OpenAI client wrapper (GPT-4o reasoning + embeddings).

Provides a thin async interface used by every agent. In local/demo mode (no endpoint
configured) it returns deterministic stub completions so the swarm runs offline.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    def __init__(self) -> None:
        self._enabled = bool(settings.azure_openai_endpoint)
        self._client = None

    def _ensure(self):
        if self._client is not None:
            return self._client
        from openai import AsyncAzureOpenAI

        if settings.azure_openai_api_key:
            self._client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                api_key=settings.azure_openai_api_key,
                api_version=settings.azure_openai_api_version,
            )
        else:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            self._client = AsyncAzureOpenAI(
                azure_endpoint=settings.azure_openai_endpoint,
                azure_ad_token_provider=token_provider,
                api_version=settings.azure_openai_api_version,
            )
        return self._client

    async def reason_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        fallback: Any = None,
    ) -> Any:
        """Call GPT-4o expecting a JSON object/array. Returns parsed JSON."""
        if not self._enabled:
            logger.info("OpenAI not configured — returning fallback stub.")
            return fallback

        client = self._ensure()
        resp = await client.chat.completions.create(
            model=settings.azure_openai_deployment,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Model returned non-JSON; using fallback.")
            return fallback

    async def embed(self, text: str) -> list[float]:
        if not self._enabled:
            return [0.0] * 8
        client = self._ensure()
        resp = await client.embeddings.create(
            model=settings.azure_openai_embed_deployment, input=text
        )
        return resp.data[0].embedding


openai_client = OpenAIClient()
