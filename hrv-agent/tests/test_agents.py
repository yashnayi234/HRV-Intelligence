"""Unit tests for the anomaly detection agent node."""

from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.nodes.anomaly_detection import _check_record, anomaly_detection_node
from agents.state import HRVAgentState
from data.models import HRVRecord


def make_record(**overrides) -> HRVRecord:
    """Create a valid HRVRecord with healthy defaults, optionally overriding fields."""
    defaults = {
        "SI > 1": 0, "Sepsis3": 0,
        "Mean.rate": 75.0, "Coefficient.of.variation": 0.05,
        "mean": 0.80, "median": 0.80,
        "Poincar..SD1": 0.03, "Poincar..SD2": 0.06,
        "LF.HF.ratio.LombScargle": 1.5, "LF.Power.LombScargle": 0.002,
        "HF.Power.LombScargle": 0.003, "VLF.Power.LombScargle": 0.001,
        "Power.Law.Slope.LombScargle": -1.0, "Power.Law.Y.Intercept.LombScargle": 2.0,
        "DFA.Alpha.1": 1.0, "DFA.Alpha.2": 1.1, "DFA.AUC": 0.5,
        "Largest.Lyapunov.exponent": 0.1, "Correlation.dimension": 2.5,
        "Multiscale.Entropy": 1.5, "Complexity": 80.0, "Hurst.exponent": 0.7,
        "shannEn": 3.5, "QSE": 0.5, "KLPE": 0.8,
        "SymDp0_2": 0.1, "SymDp1_2": 0.1, "SymDp2_2": 0.1,
        "SymDfw_2": 0.5, "SymDse_2": 1.0, "SymDce_2": 0.5,
        "eScaleE": 1.0, "pR": 0.1, "pD": 0.1, "dlmax": 5.0,
        "sedl": 0.5, "pDpR": 0.05, "pL": 0.05, "vlmax": 3.0, "sevl": 0.5,
        "PSeo": 0.5, "Teo": 0.3, "formF": 0.5, "gcount": 10.0,
        "sgridAND": 0.1, "sgridTAU": 0.1, "sgridWGT": 0.1,
        "aFdP": 0.1, "fFdP": 0.1, "IoV": 0.5, "AsymI": 0.1,
        "CSI": 1.0, "CVI": 1.0, "ARerr": 0.01, "histSI": 0.5,
        "MultiFractal_c1": 0.5, "MultiFractal_c2": 0.1,
        "SDLEalpha": 0.5, "SDLEmean": 0.5,
    }
    defaults.update(overrides)
    return HRVRecord.model_validate(defaults)


def test_healthy_record_no_anomalies() -> None:
    """Healthy record should produce no anomalies."""
    rec = make_record()
    anomalies = _check_record(rec)
    assert anomalies == [], f"Healthy record should have no anomalies, got: {anomalies}"


def test_critical_lf_hf_flagged() -> None:
    """LF/HF > 5.0 should trigger critical anomaly."""
    rec = make_record(**{"LF.HF.ratio.LombScargle": 6.5})
    anomalies = _check_record(rec)
    assert any(a.severity == "critical" for a in anomalies)
    assert any(a.feature == "LF.HF.ratio.LombScargle" for a in anomalies)


def test_low_multiscale_entropy_critical() -> None:
    """MSE < 0.8 should be critical."""
    rec = make_record(**{"Multiscale.Entropy": 0.6})
    anomalies = _check_record(rec)
    crits = [a for a in anomalies if a.feature == "Multiscale.Entropy" and a.severity == "critical"]
    assert len(crits) >= 1


def test_sd1_vagal_withdrawal_critical() -> None:
    """SD1 < 0.004 should be critical."""
    rec = make_record(**{"Poincar..SD1": 0.002})
    anomalies = _check_record(rec)
    crits = [a for a in anomalies if a.feature == "Poincar..SD1" and a.severity == "critical"]
    assert len(crits) >= 1


def test_dfa_fractal_breakdown_critical() -> None:
    """DFA alpha1 < 0.4 should be critical."""
    rec = make_record(**{"DFA.Alpha.1": 0.3})
    anomalies = _check_record(rec)
    crits = [a for a in anomalies if a.feature == "DFA.Alpha.1" and a.severity == "critical"]
    assert len(crits) >= 1


def test_deduplication_keeps_highest_severity() -> None:
    """When LF/HF triggers both high and critical, only critical should remain."""
    rec = make_record(**{"LF.HF.ratio.LombScargle": 6.0})  # > 5.0 (critical)
    anomalies = _check_record(rec)
    lf_hf_events = [a for a in anomalies if a.feature == "LF.HF.ratio.LombScargle"]
    assert len(lf_hf_events) == 1
    assert lf_hf_events[0].severity == "critical"


@pytest.mark.asyncio
async def test_anomaly_detection_node_integration() -> None:
    """Test node integration with a sepsis-like record."""
    rec = make_record(**{
        "LF.HF.ratio.LombScargle": 6.0,
        "Multiscale.Entropy": 0.7,
        "Poincar..SD1": 0.003,
        "DFA.Alpha.1": 0.35,
    })
    state: HRVAgentState = {
        "records": [rec],
        "batch_size": 1,
        "user_query": "",
        "analysis_mode": "full",
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

    updated = await anomaly_detection_node(state)
    assert "anomalies" in updated
    assert len(updated["anomalies"]) >= 3
    critical_anomalies = [a for a in updated["anomalies"] if a.severity == "critical"]
    assert len(critical_anomalies) >= 2
