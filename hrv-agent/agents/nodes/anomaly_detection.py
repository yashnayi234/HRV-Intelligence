"""Anomaly detection node — rule-based clinical threshold checks."""

from __future__ import annotations

import time
from typing import Any

import structlog

from agents.state import HRVAgentState
from data.models import AnomalyEvent, HRVRecord

logger = structlog.get_logger(__name__)

# ── Hard clinical thresholds ─────────────────────────────────────────────────
# Based on published HRV-sepsis literature embedded in the domain spec.

THRESHOLD_RULES: list[dict[str, Any]] = [
    {
        "feature": "LF.HF.ratio.LombScargle",
        "attr": "lf_hf_ratio",
        "condition": "gt",
        "threshold": 5.0,
        "severity": "critical",
        "description": (
            "LF/HF ratio {val:.2f} > 5.0 — severe sympathetic hyperactivation; "
            "autonomic imbalance consistent with septic shock physiology."
        ),
    },
    {
        "feature": "LF.HF.ratio.LombScargle",
        "attr": "lf_hf_ratio",
        "condition": "gt",
        "threshold": 3.0,
        "severity": "high",
        "description": (
            "LF/HF ratio {val:.2f} > 3.0 — sympathetic dominance; "
            "parasympathetic withdrawal is an early sepsis signal."
        ),
    },
    {
        "feature": "DFA.Alpha.1",
        "attr": "dfa_alpha1",
        "condition": "lt",
        "threshold": 0.4,
        "severity": "critical",
        "description": (
            "DFA α1 = {val:.3f} < 0.4 — severe fractal breakdown; "
            "loss of 1/f scaling indicates critical autonomic dysfunction."
        ),
    },
    {
        "feature": "DFA.Alpha.1",
        "attr": "dfa_alpha1",
        "condition": "gt",
        "threshold": 1.8,
        "severity": "high",
        "description": (
            "DFA α1 = {val:.3f} > 1.8 — fractal over-correlation; "
            "loss of normal 1/f dynamics, associated with critical illness."
        ),
    },
    {
        "feature": "Multiscale.Entropy",
        "attr": "multiscale_entropy",
        "condition": "lt",
        "threshold": 0.8,
        "severity": "critical",
        "description": (
            "Multiscale Entropy = {val:.3f} < 0.8 — complexity collapse; "
            "severe reduction in physiological complexity predicts organ failure."
        ),
    },
    {
        "feature": "Multiscale.Entropy",
        "attr": "multiscale_entropy",
        "condition": "lt",
        "threshold": 1.0,
        "severity": "high",
        "description": (
            "Multiscale Entropy = {val:.3f} < 1.0 — complexity reduction; "
            "associated with critical illness and reduced adaptability."
        ),
    },
    {
        "feature": "Poincar..SD1",
        "attr": "poincare_sd1",
        "condition": "lt",
        "threshold": 0.004,
        "severity": "critical",
        "description": (
            "SD1 = {val:.5f} < 0.004 — near-complete vagal withdrawal; "
            "parasympathetic branch suppressed, consistent with sepsis."
        ),
    },
    {
        "feature": "Poincar..SD1",
        "attr": "poincare_sd1",
        "condition": "lt",
        "threshold": 0.005,
        "severity": "high",
        "description": (
            "SD1 = {val:.5f} < 0.005 — significant vagal withdrawal; "
            "short-term HRV severely reduced."
        ),
    },
    {
        "feature": "Complexity",
        "attr": "complexity",
        "condition": "lt",
        "threshold": 50.0,
        "severity": "high",
        "description": (
            "Complexity index = {val:.1f} < 50 — significant physiological stress; "
            "composite complexity collapse may indicate organ failure risk."
        ),
    },
    {
        "feature": "Poincar..SD2",
        "attr": "poincare_sd2",
        "condition": "lt",
        "threshold": 0.020,
        "severity": "high",
        "description": (
            "SD2 = {val:.5f} < 0.020 — reduced long-term HRV variability; "
            "sympathovagal balance severely disrupted."
        ),
    },
]


def _check_record(record: HRVRecord) -> list[AnomalyEvent]:
    """Apply all threshold rules to a single record."""
    anomalies: list[AnomalyEvent] = []

    for rule in THRESHOLD_RULES:
        val: float = getattr(record, rule["attr"])
        triggered = (
            (rule["condition"] == "gt" and val > rule["threshold"])
            or (rule["condition"] == "lt" and val < rule["threshold"])
        )
        if triggered:
            anomalies.append(
                AnomalyEvent(
                    feature=rule["feature"],
                    value=val,
                    threshold=rule["threshold"],
                    severity=rule["severity"],
                    clinical_description=rule["description"].format(val=val),
                )
            )

    # Deduplicate: keep only the highest severity per feature
    best: dict[str, AnomalyEvent] = {}
    severity_rank: dict[str, int] = {"warning": 0, "high": 1, "critical": 2}
    for event in anomalies:
        existing = best.get(event.feature)
        if existing is None or severity_rank[event.severity] > severity_rank[existing.severity]:
            best[event.feature] = event

    return list(best.values())


async def anomaly_detection_node(state: HRVAgentState) -> dict[str, Any]:
    """
    Runs hard clinical threshold checks on all records.

    No LLM needed — pure rule-based detection using published HRV-sepsis thresholds.
    Outputs list[AnomalyEvent] sorted by severity descending.
    """
    start = time.perf_counter()
    records: list[HRVRecord] = state["records"]

    all_anomalies: list[AnomalyEvent] = []
    for record in records:
        all_anomalies.extend(_check_record(record))

    # Sort: critical first, then high, then warning
    severity_rank: dict[str, int] = {"warning": 0, "high": 1, "critical": 2}
    all_anomalies.sort(key=lambda e: severity_rank.get(e.severity, 0), reverse=True)

    latency = (time.perf_counter() - start) * 1000
    metadata = state.get("processing_metadata", {})
    metadata.setdefault("node_path", []).append("anomaly_detection_node")
    metadata["anomaly_detection_latency_ms"] = latency
    metadata["anomaly_count"] = len(all_anomalies)

    logger.info(
        "Anomaly detection complete",
        n_anomalies=len(all_anomalies),
        critical_count=sum(1 for a in all_anomalies if a.severity == "critical"),
        latency_ms=f"{latency:.1f}",
    )

    return {
        "anomalies": all_anomalies,
        "processing_metadata": metadata,
    }
