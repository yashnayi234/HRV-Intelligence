"""Synthesis node — final structured clinical briefing using Claude Sonnet."""

from __future__ import annotations

import time
from typing import Any

import structlog

from agents.state import HRVAgentState
from data.models import AnomalyEvent, RiskLevel

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """Synthesize all upstream agent outputs into a structured clinical briefing.
Format: (1) Risk Summary [1 sentence], (2) Key HRV Findings [3 bullet points
with specific values], (3) Clinical Interpretation [2–3 sentences],
(4) Recommendations [numbered list]. Total length: 200–300 words."""


def _build_synthesis_prompt(state: HRVAgentState) -> str:
    """Build synthesis prompt from all upstream agent outputs."""
    records = state.get("records", [])
    risk_levels = state.get("risk_levels", [])
    risk_scores = state.get("risk_scores", [])
    anomalies = state.get("anomalies", [])
    interpretation = state.get("clinical_interpretation", "")
    recommendations = state.get("recommendations", [])
    feature_summary = state.get("feature_summary", {})
    dominant_patterns = state.get("dominant_patterns", [])

    primary_risk = risk_levels[0].value if risk_levels else "unknown"
    primary_prob = risk_scores[0] if risk_scores else 0.0

    anomaly_text = "\n".join(
        f"  [{a.severity.upper()}] {a.feature}={a.value:.4f}"
        for a in anomalies[:5]
    )

    rec_text = "\n".join(
        f"  {i+1}. {r}" for i, r in enumerate(recommendations[:5])
    )

    return f"""
Synthesize into a structured clinical briefing:

Risk Level: {primary_risk.upper()} (probability: {primary_prob:.1%})
Dominant Patterns: {', '.join(dominant_patterns)}

Anomalies Detected:
{anomaly_text if anomaly_text else '  None'}

Clinical Interpretation:
{interpretation}

Recommendations:
{rec_text}

Feature Summary:
  LF/HF: {feature_summary.get('frequency', {}).get('mean_lf_hf', 'N/A')}
  MSE: {feature_summary.get('nonlinear', {}).get('mean_multiscale_entropy', 'N/A')}
  SD1/SD2: {feature_summary.get('poincare', {}).get('sd1_sd2_ratio', 'N/A')}

Format the final briefing as specified in the system prompt.
"""


async def synthesis_node(state: HRVAgentState) -> dict[str, Any]:
    """
    Synthesizes all agent outputs into a final structured clinical coach response.

    Uses Claude Sonnet for natural-language synthesis. Falls back to a template.
    """
    start = time.perf_counter()

    coach_response = ""
    input_tokens = 0
    output_tokens = 0

    try:
        from bedrock.client import llm_sonnet
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt = _build_synthesis_prompt(state)
        response = await llm_sonnet.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        coach_response = str(response.content)

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)

    except Exception as exc:
        logger.warning("Bedrock unavailable — building template synthesis", error=str(exc))
        risk_levels = state.get("risk_levels", [RiskLevel.LOW])
        risk_scores = state.get("risk_scores", [0.0])
        anomalies = state.get("anomalies", [])
        recommendations = state.get("recommendations", [])
        interpretation = state.get("clinical_interpretation", "")
        dominant_patterns = state.get("dominant_patterns", [])

        primary_risk = risk_levels[0].value if risk_levels else "unknown"
        primary_prob = risk_scores[0] if risk_scores else 0.0

        anomaly_bullets = "\n".join(
            f"  • [{a.severity.upper()}] {a.feature}: {a.clinical_description[:80]}"
            for a in anomalies[:3]
        )
        rec_list = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(recommendations[:4]))

        coach_response = (
            f"**RISK SUMMARY**: Patient classified as {primary_risk.upper()} risk "
            f"(sepsis probability: {primary_prob:.1%}).\n\n"
            f"**KEY HRV FINDINGS**:\n{anomaly_bullets}\n\n"
            f"**CLINICAL INTERPRETATION**: {interpretation}\n\n"
            f"**RECOMMENDATIONS**:\n{rec_list}"
        )

    latency = (time.perf_counter() - start) * 1000
    metadata = state.get("processing_metadata", {})
    metadata.setdefault("node_path", []).append("synthesis_node")
    metadata["synthesis_latency_ms"] = latency
    metadata["synthesis_input_tokens"] = input_tokens
    metadata["synthesis_output_tokens"] = output_tokens
    metadata["total_latency_ms"] = (time.perf_counter() - metadata.get("start_time", start)) * 1000

    # Compute total Bedrock cost
    haiku_in = metadata.get("feature_analysis_input_tokens", 0)
    haiku_out = metadata.get("feature_analysis_output_tokens", 0)
    sonnet_in = (
        metadata.get("interpretation_input_tokens", 0)
        + metadata.get("synthesis_input_tokens", 0)
    )
    sonnet_out = (
        metadata.get("interpretation_output_tokens", 0)
        + metadata.get("synthesis_output_tokens", 0)
    )
    cost_haiku = haiku_in * 0.25 / 1e6 + haiku_out * 1.25 / 1e6
    cost_sonnet = sonnet_in * 3.0 / 1e6 + sonnet_out * 15.0 / 1e6
    metadata["estimated_bedrock_cost_usd"] = round(cost_haiku + cost_sonnet, 6)

    logger.info(
        "Synthesis complete",
        latency_ms=f"{latency:.1f}",
        total_latency_ms=f"{metadata['total_latency_ms']:.1f}",
        estimated_cost_usd=metadata["estimated_bedrock_cost_usd"],
    )

    return {
        "coach_response": coach_response,
        "processing_metadata": metadata,
    }
