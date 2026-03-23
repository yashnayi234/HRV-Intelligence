"""RAG retrieval node — LanceDB similarity search for similar historical cases."""

from __future__ import annotations

import os
import time
from typing import Any

import structlog

from agents.state import HRVAgentState
from data.models import HRVRecord, RiskLevel

logger = structlog.get_logger(__name__)


def _record_to_text(record: HRVRecord) -> str:
    """Convert HRV record to text representation for embedding."""
    return (
        f"Patient HRV: HR={record.mean_rate:.1f}bpm, "
        f"SD1={record.poincare_sd1:.4f}, SD2={record.poincare_sd2:.4f}, "
        f"LF/HF={record.lf_hf_ratio:.2f}, DFA_alpha1={record.dfa_alpha1:.3f}, "
        f"MSE={record.multiscale_entropy:.3f}, Complexity={record.complexity:.1f}, "
        f"Sepsis={record.sepsis3}"
    )


async def rag_retrieval_node(state: HRVAgentState) -> dict[str, Any]:
    """
    Queries LanceDB for top-5 historically similar HRV cases.

    Falls back to empty list if LanceDB not initialized yet.
    Skipped automatically for analysis_mode="quick" via graph routing.
    """
    start = time.perf_counter()
    records: list[HRVRecord] = state["records"]

    similar_cases: list[dict[str, Any]] = []

    try:
        # Lazy import to avoid hard dependency if LanceDB not configured
        from data.vector_store import HRVVectorStore
        store = HRVVectorStore()
        if store.is_ready():
            for i, record in enumerate(records[:3]):   # Top-3 records only for speed
                text = _record_to_text(record)
                results = await store.similarity_search(text, k=5)
                similar_cases.extend(results)
    except Exception as exc:
        logger.warning("RAG retrieval failed — proceeding without similar cases", error=str(exc))

    latency = (time.perf_counter() - start) * 1000
    metadata = state.get("processing_metadata", {})
    metadata.setdefault("node_path", []).append("rag_retrieval_node")
    metadata["rag_latency_ms"] = latency

    logger.info(
        "RAG retrieval complete",
        n_similar_cases=len(similar_cases),
        latency_ms=f"{latency:.1f}",
    )

    return {
        "similar_cases": similar_cases,
        "processing_metadata": metadata,
    }
