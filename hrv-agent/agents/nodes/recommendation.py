"""Recommendation node — generates priority-ordered clinical recommendations using Sonnet."""

from __future__ import annotations

import time
from typing import Any

import structlog

from agents.state import HRVAgentState
from data.models import RiskLevel

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are a critical care decision support AI. Based on HRV risk assessment,
generate 3–5 specific, priority-ordered clinical recommendations.
For CRITICAL risk: lead with immediate escalation language.
For HIGH risk: focus on monitoring frequency and intervention readiness.
For MODERATE: recommend re-assessment timeline and conservative interventions.
For LOW: provide maintenance guidance. Be specific, not generic."""


_FALLBACK_RECOMMENDATIONS: dict[str, list[str]] = {
    "critical": [
        "IMMEDIATE: Escalate to ICU attending — HRV pattern consistent with septic shock.",
        "Initiate Surviving Sepsis Campaign bundle: blood cultures, IV antibiotics within 1 hour.",
        "Continuous hemodynamic monitoring: arterial line, central venous pressure.",
        "Reassess every 15 minutes; prepare for vasopressor support if MAP < 65 mmHg.",
        "Repeat HRV analysis and lactate measurement in 30 minutes.",
    ],
    "high": [
        "Escalate to senior physician for immediate bedside review.",
        "Continuous cardiac monitoring and pulse oximetry.",
        "Obtain blood cultures, CBC, lactate, and CRP within 1 hour.",
        "Re-assess HRV every 2 hours — watch for trajectory toward critical.",
        "Consider early antibiotic treatment per institutional sepsis protocol.",
    ],
    "moderate": [
        "Schedule physician re-assessment within 4 hours.",
        "Obtain inflammatory markers: CBC, CRP, procalcitonin.",
        "Increase nursing assessment frequency to every 2 hours.",
        "Review medication list for autonomic-modulating agents.",
        "Repeat HRV analysis in 6 hours to assess trajectory.",
    ],
    "low": [
        "Continue routine monitoring per standard care protocol.",
        "Repeat HRV assessment at next scheduled check-in (24 hours).",
        "Encourage restorative activities: adequate sleep, hydration, reduced stress.",
        "Document baseline HRV values for longitudinal tracking.",
    ],
}


async def recommendation_node(state: HRVAgentState) -> dict[str, Any]:
    """
    Generates priority-ordered clinical recommendations using Claude Sonnet.

    Falls back to evidence-based template recommendations per risk level.
    """
    start = time.perf_counter()

    risk_levels = state.get("risk_levels", [RiskLevel.LOW])
    primary_risk = risk_levels[0] if risk_levels else RiskLevel.LOW
    anomalies = state.get("anomalies", [])
    interpretation = state.get("clinical_interpretation", "")

    recommendations: list[str] = []

    try:
        from bedrock.client import llm_sonnet
        from langchain_core.messages import HumanMessage, SystemMessage

        anomaly_text = "\n".join(
            f"  - [{a.severity.upper()}] {a.feature}: {a.clinical_description}"
            for a in anomalies[:5]
        )

        prompt = f"""
Risk Level: {primary_risk.value.upper()}
Clinical Interpretation: {interpretation[:500]}

Detected Anomalies:
{anomaly_text if anomaly_text else "None"}

Generate 3–5 specific, priority-ordered clinical recommendations for this HRV risk profile.
Return as a numbered list only.
"""
        response = await llm_sonnet.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        raw = str(response.content)
        # Parse numbered list
        lines = [line.strip() for line in raw.split("\n") if line.strip()]
        recommendations = [line for line in lines if line[0].isdigit() or line.startswith("-")]
        if not recommendations:
            recommendations = [raw]

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            pass  # token usage is recorded elsewhere if needed

    except Exception as exc:
        logger.warning("Bedrock unavailable — using fallback recommendations", error=str(exc))
        recommendations = _FALLBACK_RECOMMENDATIONS.get(primary_risk.value, [])

    latency = (time.perf_counter() - start) * 1000
    metadata = state.get("processing_metadata", {})
    metadata.setdefault("node_path", []).append("recommendation_node")
    metadata["recommendation_latency_ms"] = latency

    logger.info(
        "Recommendations generated",
        n_recommendations=len(recommendations),
        risk_level=primary_risk.value,
        latency_ms=f"{latency:.1f}",
    )

    return {
        "recommendations": recommendations,
        "processing_metadata": metadata,
    }
