"""AWS Bedrock client — ChatBedrockConverse for us.* cross-region inference models."""

from __future__ import annotations

import os
from functools import lru_cache

import boto3
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

# ── Model IDs ─────────────────────────────────────────────────────────────────
SONNET_MODEL   = os.getenv("BEDROCK_SONNET_MODEL",   "us.anthropic.claude-3-5-sonnet-20241022-v2:0")
HAIKU_MODEL    = os.getenv("BEDROCK_HAIKU_MODEL",    "us.anthropic.claude-3-5-haiku-20241022-v1:0")
SONNET_4_MODEL = os.getenv("BEDROCK_SONNET_4_MODEL", "us.anthropic.claude-sonnet-4-20250514-v1:0")

AWS_REGION = os.getenv("AWS_REGION", "us-west-2")


@lru_cache(maxsize=1)
def _cached_bedrock_client() -> boto3.client:
    """Singleton boto3 Bedrock Runtime client."""
    return boto3.client(
        "bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


# ── LLM clients (ChatBedrockConverse — supports us.* cross-region IDs) ────────

def get_llm_sonnet():  # type: ignore[return]
    """Claude 3.5 Sonnet v2 — deep clinical reasoning (interpretation, synthesis)."""
    from langchain_aws import ChatBedrockConverse
    return ChatBedrockConverse(
        model=SONNET_MODEL,
        client=_cached_bedrock_client(),
        temperature=0.1,
        max_tokens=1500,
    )


def get_llm_haiku():  # type: ignore[return]
    """Claude 3.5 Haiku — fast routing, feature summaries, trend analysis."""
    from langchain_aws import ChatBedrockConverse
    return ChatBedrockConverse(
        model=HAIKU_MODEL,
        client=_cached_bedrock_client(),
        temperature=0.0,
        max_tokens=600,
    )


def get_embeddings():  # type: ignore[return]
    """Amazon Titan Text Embeddings v2 — for LanceDB vector store."""
    from langchain_aws import BedrockEmbeddings
    return BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0",
        client=_cached_bedrock_client(),
    )


# ── Lazy accessor ─────────────────────────────────────────────────────────────

class _LazyLLM:
    """Initializes the Bedrock client on first use."""

    def __init__(self, getter):  # type: ignore[type-arg]
        self._getter = getter
        self._instance = None

    def _get(self):  # type: ignore[return]
        if self._instance is None:
            self._instance = self._getter()
        return self._instance

    def __getattr__(self, name: str):  # type: ignore[return]
        return getattr(self._get(), name)

    async def ainvoke(self, *args, **kwargs):  # type: ignore[override]
        return await self._get().ainvoke(*args, **kwargs)

    def invoke(self, *args, **kwargs):  # type: ignore[override]
        return self._get().invoke(*args, **kwargs)


llm_sonnet = _LazyLLM(get_llm_sonnet)
llm_haiku  = _LazyLLM(get_llm_haiku)
embeddings = _LazyLLM(get_embeddings)


# ── Retry decorator ───────────────────────────────────────────────────────────

def with_bedrock_retry(func):  # type: ignore[return,type-arg]
    """Wrap async function with exponential backoff (3 attempts, 2–10 s)."""
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )(func)
