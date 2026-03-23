"""LangGraph agent state definition for the HRV multi-agent pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

from data.models import AnomalyEvent, HRVRecord, RiskLevel


class HRVAgentState(TypedDict):
    """Shared mutable state passed between all agent nodes."""

    # ── Input ─────────────────────────────────────────────────────────────────
    records: list[HRVRecord]
    batch_size: int
    user_query: str
    analysis_mode: str  # "quick" | "full" | "clinical"

    # ── Feature analysis output ───────────────────────────────────────────────
    feature_summary: dict[str, Any]

    # ── Anomaly detection output ──────────────────────────────────────────────
    anomalies: list[AnomalyEvent]

    # ── ML scoring output ──────────────────────────────────────────────────────
    risk_scores: list[float]
    risk_levels: list[RiskLevel]
    dominant_patterns: list[str]
    critical_features: list[str]

    # ── RAG retrieval output ──────────────────────────────────────────────────
    similar_cases: list[dict[str, Any]]

    # ── Clinical reasoning output ─────────────────────────────────────────────
    clinical_interpretation: str
    recommendations: list[str]
    coach_response: str

    # ── Observability ─────────────────────────────────────────────────────────
    processing_metadata: dict[str, Any]   # latency, token cost, node path
