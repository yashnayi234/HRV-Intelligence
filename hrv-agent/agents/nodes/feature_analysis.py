"""Feature analysis node — group-level summaries using Haiku for fast inference."""

from __future__ import annotations

import time
from typing import Any

import structlog

from agents.state import HRVAgentState
from data.models import HRVRecord

logger = structlog.get_logger(__name__)


def _compute_group_stats(records: list[HRVRecord]) -> dict[str, Any]:
    """Compute aggregate statistics across the batch for each feature group."""
    n = len(records)
    if n == 0:
        return {}

    def avg(vals: list[float]) -> float:
        return sum(vals) / len(vals)

    mean_rates = [r.mean_rate for r in records]
    sd1s = [r.poincare_sd1 for r in records]
    sd2s = [r.poincare_sd2 for r in records]
    lf_hf = [r.lf_hf_ratio for r in records]
    hf_powers = [r.hf_power for r in records]
    dfa1s = [r.dfa_alpha1 for r in records]
    mses = [r.multiscale_entropy for r in records]
    complexities = [r.complexity for r in records]
    shannon = [r.shann_en for r in records]

    return {
        "time_domain": {
            "mean_heart_rate": avg(mean_rates),
            "mean_rate_range": [min(mean_rates), max(mean_rates)],
        },
        "poincare": {
            "mean_sd1": avg(sd1s),
            "mean_sd2": avg(sd2s),
            "sd1_sd2_ratio": avg(sd1s) / (avg(sd2s) + 1e-9),
        },
        "frequency": {
            "mean_lf_hf": avg(lf_hf),
            "mean_hf_power": avg(hf_powers),
            "pct_elevated_lf_hf": sum(v > 3.0 for v in lf_hf) / n,
        },
        "nonlinear": {
            "mean_dfa_alpha1": avg(dfa1s),
            "mean_multiscale_entropy": avg(mses),
            "mean_complexity": avg(complexities),
            "pct_fractal_breakdown": sum(v < 0.5 or v > 1.5 for v in dfa1s) / n,
        },
        "entropy": {
            "mean_shannon_entropy": avg(shannon),
        },
    }


async def feature_analysis_node(state: HRVAgentState) -> dict[str, Any]:
    """
    Computes group-level HRV summaries across the batch.

    For LLM-augmented path: sends group summaries to Haiku for natural-language flag.
    In the initial implementation, uses deterministic group stats.
    """
    start = time.perf_counter()
    records: list[HRVRecord] = state["records"]

    feature_summary = _compute_group_stats(records)

    # Identify dominant deviation patterns
    dominant_patterns: list[str] = []
    critical_features: list[str] = []

    freq = feature_summary.get("frequency", {})
    if freq.get("mean_lf_hf", 0) > 3.0:
        dominant_patterns.append("sympathetic_hyperactivation")
        critical_features.append("LF.HF.ratio.LombScargle")

    nonlin = feature_summary.get("nonlinear", {})
    if nonlin.get("mean_multiscale_entropy", 1.5) < 1.0:
        dominant_patterns.append("complexity_collapse")
        critical_features.append("Multiscale.Entropy")

    if nonlin.get("pct_fractal_breakdown", 0) > 0.3:
        dominant_patterns.append("fractal_dynamics_loss")
        critical_features.append("DFA.Alpha.1")

    poincare = feature_summary.get("poincare", {})
    if poincare.get("mean_sd1", 1.0) < 0.005:
        dominant_patterns.append("vagal_withdrawal")
        critical_features.append("Poincar..SD1")

    latency = (time.perf_counter() - start) * 1000
    metadata = state.get("processing_metadata", {})
    metadata.setdefault("node_path", []).append("feature_analysis_node")
    metadata["feature_analysis_latency_ms"] = latency

    logger.info(
        "Feature analysis complete",
        patterns=dominant_patterns,
        latency_ms=f"{latency:.1f}",
    )

    return {
        "feature_summary": feature_summary,
        "dominant_patterns": dominant_patterns,
        "critical_features": critical_features,
        "processing_metadata": metadata,
    }
