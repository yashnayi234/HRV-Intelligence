"""Clinical interpretation node — uses Claude Sonnet for deep HRV analysis."""

from __future__ import annotations

import time
from typing import Any

import structlog

from agents.state import HRVAgentState
from data.models import AnomalyEvent, HRVRecord, RiskLevel

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are a clinical HRV scientist specializing in critical care and sepsis.
You have access to 59 HRV biomarkers from a patient record. Interpret the
pattern in terms of autonomic nervous system balance, fractal dynamics, and
entropy. Reference specific feature values. Be precise and clinical.
Sepsis correlates with: reduced SD1/SD2, elevated LF/HF ratio (>3), low
Multiscale Entropy (<1.0), DFA Alpha.1 deviation from 1.0, and complexity
collapse. Keep response to 4–6 sentences."""


def _build_interpretation_prompt(
    records: list[HRVRecord],
    anomalies: list[AnomalyEvent],
    risk_scores: list[float],
    risk_levels: list[RiskLevel],
    feature_summary: dict[str, Any],
    similar_cases: list[dict[str, Any]],
) -> str:
    """Build the clinical interpretation prompt from all upstream context."""
    first = records[0] if records else None
    primary_risk = risk_levels[0] if risk_levels else RiskLevel.LOW
    primary_prob = risk_scores[0] if risk_scores else 0.0

    anomaly_text = "\n".join(
        f"  - [{a.severity.upper()}] {a.feature}={a.value:.4f}: {a.clinical_description}"
        for a in anomalies[:5]
    )

    similar_text = ""
    if similar_cases:
        similar_text = "\nHistorically similar cases:\n" + "\n".join(
            f"  - Sepsis={c.get('sepsis3', '?')}, "
            f"LF/HF={c.get('lf_hf_ratio', '?'):.2f}, "
            f"similarity={c.get('_distance', 0):.3f}"
            for c in similar_cases[:3]
        )

    if first is None:
        return "No records provided for interpretation."

    return f"""
Patient HRV Analysis Request:
  Records analyzed: {len(records)}
  Primary risk level: {primary_risk.value.upper()}
  Sepsis probability: {primary_prob:.1%}

Key biomarkers (first record):
  Mean HR: {first.mean_rate:.1f} bpm
  SD1 (vagal tone): {first.poincare_sd1:.5f}
  SD2 (sympathovagal): {first.poincare_sd2:.5f}
  LF/HF ratio: {first.lf_hf_ratio:.3f}
  DFA Alpha.1: {first.dfa_alpha1:.3f}
  Multiscale Entropy: {first.multiscale_entropy:.3f}
  Complexity: {first.complexity:.1f}
  Shannon Entropy: {first.shann_en:.4f}

Detected anomalies:
{anomaly_text if anomaly_text else '  None detected'}
{similar_text}

Feature group summary:
  Time-domain: Mean HR = {feature_summary.get('time_domain', {}).get('mean_heart_rate', 'N/A'):.1f} bpm
  Poincaré: SD1/SD2 = {feature_summary.get('poincare', {}).get('sd1_sd2_ratio', 'N/A'):.4f}
  Frequency: Mean LF/HF = {feature_summary.get('frequency', {}).get('mean_lf_hf', 'N/A'):.3f}
  Nonlinear: Mean MSE = {feature_summary.get('nonlinear', {}).get('mean_multiscale_entropy', 'N/A'):.3f}

Provide a 4–6 sentence clinical interpretation of this HRV pattern.
"""


async def clinical_interpretation_node(state: HRVAgentState) -> dict[str, Any]:
    """
    Generates clinical HRV interpretation using Claude Sonnet 3.5.

    Falls back to deterministic interpretation if Bedrock not available.
    """
    start = time.perf_counter()

    prompt = _build_interpretation_prompt(
        records=state["records"],
        anomalies=state.get("anomalies", []),
        risk_scores=state.get("risk_scores", []),
        risk_levels=state.get("risk_levels", []),
        feature_summary=state.get("feature_summary", {}),
        similar_cases=state.get("similar_cases", []),
    )

    interpretation = ""
    input_tokens = 0
    output_tokens = 0

    try:
        from bedrock.client import llm_sonnet
        from langchain_core.messages import HumanMessage, SystemMessage

        response = await llm_sonnet.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        interpretation = str(response.content)
        # Token usage (if available)
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = response.usage_metadata.get("input_tokens", 0)
            output_tokens = response.usage_metadata.get("output_tokens", 0)

    except Exception as exc:
        logger.warning("Bedrock unavailable — using fallback interpretation", error=str(exc))
        risk_levels = state.get("risk_levels", [])
        anomalies = state.get("anomalies", [])
        primary_risk = risk_levels[0].value if risk_levels else "unknown"
        n_critical = sum(1 for a in anomalies if a.severity == "critical")
        interpretation = (
            f"HRV analysis indicates {primary_risk.upper()} sepsis risk based on pattern analysis. "
            f"{n_critical} critical anomalies were detected in the autonomic biomarker profile. "
            f"Elevated sympathovagal imbalance and reduced complexity are the primary concerns. "
            f"Clinical correlation and physician review is strongly recommended."
        )

    latency = (time.perf_counter() - start) * 1000
    metadata = state.get("processing_metadata", {})
    metadata.setdefault("node_path", []).append("clinical_interpretation_node")
    metadata["interpretation_latency_ms"] = latency
    metadata["interpretation_input_tokens"] = input_tokens
    metadata["interpretation_output_tokens"] = output_tokens

    logger.info(
        "Clinical interpretation generated",
        latency_ms=f"{latency:.1f}",
        tokens_in=input_tokens,
        tokens_out=output_tokens,
    )

    return {
        "clinical_interpretation": interpretation,
        "processing_metadata": metadata,
    }
