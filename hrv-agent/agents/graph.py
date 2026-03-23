"""LangGraph StateGraph definition for the HRV multi-agent pipeline."""

from __future__ import annotations

from typing import Any, Literal

import structlog
from langgraph.graph import END, START, StateGraph

from agents.nodes.anomaly_detection import anomaly_detection_node
from agents.nodes.clinical_interpretation import clinical_interpretation_node
from agents.nodes.feature_analysis import feature_analysis_node
from agents.nodes.ml_scoring import ml_scoring_node
from agents.nodes.rag_retrieval import rag_retrieval_node
from agents.nodes.recommendation import recommendation_node
from agents.nodes.synthesis import synthesis_node
from agents.nodes.validation import data_validation_node
from agents.state import HRVAgentState
from data.models import RiskLevel

logger = structlog.get_logger(__name__)


# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_anomaly_detection(
    state: HRVAgentState,
) -> Literal["ml_scoring_node", "ml_scoring_node"]:
    """
    Route based on critical anomaly presence.

    Currently routes all to ML scoring; immediate_alert_subgraph can be wired here.
    """
    anomalies = state.get("anomalies", [])
    has_critical = any(a.severity == "critical" for a in anomalies)
    if has_critical:
        logger.warning("Critical anomalies detected — expediting pipeline")
    return "ml_scoring_node"


def route_after_ml_scoring(
    state: HRVAgentState,
) -> Literal["rag_retrieval_node", "clinical_interpretation_node"]:
    """Skip RAG retrieval if analysis_mode is 'quick'."""
    mode = state.get("analysis_mode", "full")
    if mode == "quick":
        return "clinical_interpretation_node"
    return "rag_retrieval_node"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_hrv_graph() -> StateGraph:
    """Construct and compile the HRV multi-agent LangGraph StateGraph."""
    graph = StateGraph(HRVAgentState)

    # Register all nodes
    graph.add_node("data_validation_node", data_validation_node)
    graph.add_node("feature_analysis_node", feature_analysis_node)
    graph.add_node("anomaly_detection_node", anomaly_detection_node)
    graph.add_node("ml_scoring_node", ml_scoring_node)
    graph.add_node("rag_retrieval_node", rag_retrieval_node)
    graph.add_node("clinical_interpretation_node", clinical_interpretation_node)
    graph.add_node("recommendation_node", recommendation_node)
    graph.add_node("synthesis_node", synthesis_node)

    # Entry point
    graph.add_edge(START, "data_validation_node")

    # Linear edges
    graph.add_edge("data_validation_node", "feature_analysis_node")
    graph.add_edge("feature_analysis_node", "anomaly_detection_node")

    # Conditional routing after anomaly detection (always → ML scoring for now)
    graph.add_conditional_edges(
        "anomaly_detection_node",
        route_after_anomaly_detection,
        {"ml_scoring_node": "ml_scoring_node"},
    )

    # Conditional routing after ML scoring (quick mode skips RAG)
    graph.add_conditional_edges(
        "ml_scoring_node",
        route_after_ml_scoring,
        {
            "rag_retrieval_node": "rag_retrieval_node",
            "clinical_interpretation_node": "clinical_interpretation_node",
        },
    )

    graph.add_edge("rag_retrieval_node", "clinical_interpretation_node")
    graph.add_edge("clinical_interpretation_node", "recommendation_node")
    graph.add_edge("recommendation_node", "synthesis_node")
    graph.add_edge("synthesis_node", END)

    return graph


# Compiled graph — import this in production code
hrv_graph = build_hrv_graph().compile()


async def run_hrv_pipeline(
    records: list[Any],
    analysis_mode: str = "full",
    user_query: str = "",
) -> HRVAgentState:
    """
    Convenience function to run the full HRV agent pipeline.

    Args:
        records: List of HRVRecord objects
        analysis_mode: "quick" | "full" | "clinical"
        user_query: Optional user question for coach mode

    Returns:
        Final HRVAgentState after pipeline completion
    """
    initial_state: HRVAgentState = {
        "records": records,
        "batch_size": len(records),
        "user_query": user_query,
        "analysis_mode": analysis_mode,
        "feature_summary": {},
        "anomalies": [],
        "risk_scores": [],
        "risk_levels": [],
        "dominant_patterns": [],
        "critical_features": [],
        "similar_cases": [],
        "clinical_interpretation": "",
        "recommendations": [],
        "coach_response": "",
        "processing_metadata": {},
    }

    final_state = await hrv_graph.ainvoke(initial_state)
    logger.info(
        "Pipeline complete",
        n_records=len(records),
        mode=analysis_mode,
        total_latency_ms=final_state.get("processing_metadata", {}).get("total_latency_ms"),
    )
    return final_state
