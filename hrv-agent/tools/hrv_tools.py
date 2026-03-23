"""5 MCP tools for the HRV Agentic Intelligence System."""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# ── Singleton resources (loaded lazily) ───────────────────────────────────────

_classifier = None
_vector_store = None
_training_stats: dict[str, dict[str, float]] = {}  # {feature: {mean, std}}
_training_percentiles: dict[str, list[float]] = {}   # {feature: [p10, p25, p50, p75, p90]}


def _get_classifier():  # type: ignore[return]
    global _classifier
    if _classifier is None:
        from ml.classifier import HRVClassifier
        _classifier = HRVClassifier()
        model_path = os.getenv("MODEL_PATH", "ml/models/xgb_hrv_v1.pkl")
        try:
            _classifier.load_model(model_path)
        except FileNotFoundError:
            pass
    return _classifier


def _get_vector_store():  # type: ignore[return]
    global _vector_store
    if _vector_store is None:
        from data.vector_store import HRVVectorStore
        _vector_store = HRVVectorStore()
    return _vector_store


# ── ANOMALY PATTERN KNOWLEDGE BASE ───────────────────────────────────────────

ANOMALY_PATTERNS: dict[str, dict[str, Any]] = {
    "sympathetic_hyperactivation": {
        "pattern": "Elevated LF/HF ratio (> 3.0–5.0) with reduced HF power",
        "clinical_meaning": (
            "Indicates autonomic imbalance with sympathetic dominance. "
            "In sepsis, this reflects the body's stress response — catecholamine surge, "
            "vagal withdrawal, and reduced parasympathetic modulation of heart rate."
        ),
        "typical_interventions": [
            "Beta-blocker titration if hemodynamically stable",
            "Address underlying sepsis with antibiotics",
            "Sedation reduction protocol in ventilated patients",
            "Early mobilization when clinically feasible",
        ],
    },
    "complexity_collapse": {
        "pattern": "Multiscale Entropy < 1.0 combined with low Complexity index",
        "clinical_meaning": (
            "Physiological complexity is a hallmark of health. Complexity collapse "
            "reflects loss of adaptive reserve, associated with organ failure, "
            "critical illness, and mortality risk in ICU patients."
        ),
        "typical_interventions": [
            "ICU admission or rapid escalation of care",
            "Continuous hemodynamic monitoring",
            "Organ function assessment (kidney, liver, coagulation)",
            "Palliative care consultation if multiple organ failure",
        ],
    },
    "fractal_dynamics_loss": {
        "pattern": "DFA Alpha.1 < 0.5 or > 1.5 (loss of 1/f scaling)",
        "clinical_meaning": (
            "Healthy cardiac dynamics exhibit 1/f fractal scaling (DFA ~1.0). "
            "Deviation in either direction indicates autonomic dysfunction. "
            "Values < 0.5 suggest uncorrelated dynamics (cardiac pathology); "
            "> 1.5 suggests over-correlated, non-adaptive dynamics (critical illness)."
        ),
        "typical_interventions": [
            "Cardiologist consultation",
            "12-lead ECG and echocardiography",
            "Cardiac biomarker panel (troponin, BNP)",
            "Continuous telemetry monitoring",
        ],
    },
    "vagal_withdrawal": {
        "pattern": "SD1 < 0.005 — very low short-term HRV",
        "clinical_meaning": (
            "SD1 reflects parasympathetic (vagal) tone. Profound SD1 reduction "
            "signifies near-complete vagal withdrawal. This is a direct biomarker "
            "of sepsis-induced autonomic dysfunction — the vagus nerve suppresses "
            "inflammatory cytokine release; its withdrawal accelerates inflammation."
        ),
        "typical_interventions": [
            "Sepsis workup — blood cultures before antibiotics",
            "Inflammatory marker panel (CRP, procalcitonin, IL-6)",
            "Consider vagus nerve stimulation in refractory cases (experimental)",
            "Early surgical consultation if septic source identified",
        ],
    },
    "entropy_reduction": {
        "pattern": "Shannon entropy and QSE both reduced",
        "clinical_meaning": (
            "Entropy reduction across multiple scales indicates a rigid, "
            "less complex heart rate pattern. Multi-domain entropy collapse "
            "carries a worse prognosis than single-domain reduction alone."
        ),
        "typical_interventions": [
            "Multi-organ support assessment",
            "Nutritional support optimization",
            "Sleep protocol to restore circadian HRV patterns",
        ],
    },
}


# ── TOOL 1: HRV Similarity Search ─────────────────────────────────────────────

async def hrv_similarity_search(
    query_features: dict[str, float],
    k: int = 5,
    filter_sepsis: bool | None = None,
) -> list[dict[str, Any]]:
    """
    Find top-K most similar HRV cases from historical LanceDB database.

    Args:
        query_features: Dict of HRV feature names to values
        k: Number of similar cases to return (default 5)
        filter_sepsis: If True/False, filter to sepsis/non-sepsis only

    Returns:
        List of similar records with similarity score and sepsis outcome
    """

    store = _get_vector_store()
    if not store.is_ready():
        logger.warning("Vector store not ready for similarity search")
        return []

    text = (
        f"Patient HRV: HR={query_features.get('mean_rate', 0):.1f}bpm, "
        f"SD1={query_features.get('poincare_sd1', 0):.4f}, "
        f"SD2={query_features.get('poincare_sd2', 0):.4f}, "
        f"LF/HF={query_features.get('lf_hf_ratio', 0):.2f}, "
        f"DFA_alpha1={query_features.get('dfa_alpha1', 1):.3f}, "
        f"MSE={query_features.get('multiscale_entropy', 0):.3f}, "
        f"Complexity={query_features.get('complexity', 0):.1f}"
    )

    return await store.similarity_search(text, k=k, filter_sepsis=filter_sepsis)


# ── TOOL 2: Risk Score Calculator ─────────────────────────────────────────────

def risk_score_calculator(
    mean_rate: float,
    lf_hf: float,
    dfa_alpha1: float,
    multiscale_entropy: float,
    complexity: float,
    poincare_sd1: float = 0.02,
) -> dict[str, Any]:
    """
    Calculate composite HRV risk score and sepsis probability.

    Returns risk_score (0–1), sepsis_probability (0–1), and risk_level string.
    """
    # Normalized composite score (heuristic, no scaler available in tool context)
    lf_hf_n = min(lf_hf / 10.0, 1.0)
    mse_n = 1.0 - min(multiscale_entropy / 3.0, 1.0)
    dfa_dev_n = min(abs(dfa_alpha1 - 1.0) / 1.0, 1.0)
    sd1_n = 1.0 - min(poincare_sd1 / 0.05, 1.0)
    complexity_n = 1.0 - min(complexity / 200.0, 1.0)
    hr_n = min((mean_rate - 60) / 120.0, 1.0)

    risk_score = float(
        0.20 * lf_hf_n
        + 0.20 * mse_n
        + 0.15 * dfa_dev_n
        + 0.15 * sd1_n
        + 0.15 * complexity_n
        + 0.15 * hr_n
    )
    risk_score = max(0.0, min(1.0, risk_score))

    # XGBoost inference if model available
    clf = _get_classifier()
    sepsis_probability = risk_score  # fallback
    if clf._model is not None:
        try:
            from data.loader import ALL_FEATURE_COLS
            row = {col: 0.0 for col in ALL_FEATURE_COLS}
            row.update({
                "Mean.rate": mean_rate,
                "LF.HF.ratio.LombScargle": lf_hf,
                "DFA.Alpha.1": dfa_alpha1,
                "Multiscale.Entropy": multiscale_entropy,
                "Complexity": complexity,
                "Poincar..SD1": poincare_sd1,
            })
            X = pd.DataFrame([row])
            result = clf.predict_single(X)
            sepsis_probability = result.sepsis_probability
        except Exception as exc:
            logger.warning("XGBoost inference failed in tool", error=str(exc))

    from ml.classifier import probability_to_risk_level
    risk_level = probability_to_risk_level(sepsis_probability).value

    return {
        "risk_score": round(risk_score, 4),
        "sepsis_probability": round(sepsis_probability, 4),
        "risk_level": risk_level,
    }


# ── TOOL 3: Anomaly Pattern Lookup ────────────────────────────────────────────

def anomaly_pattern_lookup(
    pattern_type: str,
    severity_threshold: float = 0.5,
) -> dict[str, Any]:
    """
    Look up known HRV anomaly patterns by type from the clinical knowledge base.

    Args:
        pattern_type: One of the known pattern keys
        severity_threshold: Minimum severity to include (0–1 scale)

    Returns:
        Pattern description, clinical meaning, and typical interventions
    """
    pattern = ANOMALY_PATTERNS.get(pattern_type)
    if pattern is None:
        # Try fuzzy match
        for key in ANOMALY_PATTERNS:
            if pattern_type.lower() in key.lower():
                pattern = ANOMALY_PATTERNS[key]
                break

    if pattern is None:
        available = list(ANOMALY_PATTERNS.keys())
        return {
            "error": f"Pattern '{pattern_type}' not found",
            "available_patterns": available,
        }

    return {
        "pattern_type": pattern_type,
        "pattern": pattern["pattern"],
        "clinical_meaning": pattern["clinical_meaning"],
        "typical_interventions": pattern["typical_interventions"],
    }


# ── TOOL 4: Feature Percentile Ranker ────────────────────────────────────────

def feature_percentile_ranker(
    feature_dict: dict[str, float],
) -> dict[str, Any]:
    """
    Rank a patient's HRV metrics against population percentiles.

    Requires training set statistics to be loaded.

    Args:
        feature_dict: Dict of {feature_name: value}

    Returns:
        Percentile ranks, worst features, and best features
    """
    if not _training_percentiles:
        return {
            "error": "Training population statistics not loaded yet",
            "hint": "Run trainer.py to populate stats",
        }

    percentiles_out: dict[str, float] = {}
    for feat, val in feature_dict.items():
        if feat in _training_percentiles:
            pcts = _training_percentiles[feat]
            # Rough percentile via linear interpolation
            pct = float(np.interp(val, pcts, [10, 25, 50, 75, 90]))
            percentiles_out[feat] = round(pct, 1)

    sorted_feats = sorted(percentiles_out.items(), key=lambda x: x[1])
    worst = [f for f, p in sorted_feats[:3]]
    best = [f for f, p in sorted_feats[-3:]]

    return {
        "percentiles": percentiles_out,
        "worst_features": worst,
        "best_features": best,
    }


# ── TOOL 5: Batch Trend Analyzer ─────────────────────────────────────────────

async def batch_trend_analyzer(
    records: list[dict[str, float]],
    time_labels: list[str],
) -> dict[str, Any]:
    """
    Analyze HRV trends across multiple records (e.g., hourly observations).

    Args:
        records: List of feature dicts (same patient, different time points)
        time_labels: Parallel list of time labels (e.g., ["T0", "T1", "T4", "T8"])

    Returns:
        Trend direction, inflection points, and LLM-generated forecast
    """
    if len(records) < 2:
        return {"error": "Need at least 2 records for trend analysis"}

    # Compute per-feature rolling trends
    key_features = ["lf_hf_ratio", "multiscale_entropy", "complexity", "poincare_sd1"]
    trends: dict[str, Any] = {}

    for feat in key_features:
        vals = [float(r.get(feat, 0)) for r in records]
        if len(vals) >= 2:
            slope = (vals[-1] - vals[0]) / max(len(vals) - 1, 1)
            direction = "improving" if slope < 0 and feat in ["lf_hf_ratio"] else (
                "worsening" if slope > 0 and feat in ["lf_hf_ratio"] else "stable"
            )
            trends[feat] = {
                "values": vals,
                "slope": round(slope, 6),
                "direction": direction,
            }

    # Overall trend direction
    lf_hf_trend = trends.get("lf_hf_ratio", {}).get("slope", 0)
    mse_trend = trends.get("multiscale_entropy", {}).get("slope", 0)
    overall = "deteriorating" if lf_hf_trend > 0 or mse_trend < 0 else "stable_or_improving"

    # LLM forecast (optional)
    forecast = f"HRV trajectory over {len(records)} time points appears {overall}."
    try:
        from bedrock.client import llm_haiku
        from langchain_core.messages import HumanMessage, SystemMessage

        trend_text = "\n".join(
            f"  {feat}: {trends[feat]['values']} (slope: {trends[feat]['slope']:.6f})"
            for feat in trends
        )
        prompt = f"""
Time points: {time_labels}
HRV feature trends:
{trend_text}

Provide a 2-sentence clinical forecast of where this patient's HRV trajectory is heading.
"""
        response = await llm_haiku.ainvoke([
            SystemMessage(content="You are a clinical HRV trend analyst."),
            HumanMessage(content=prompt),
        ])
        forecast = str(response.content)
    except Exception:
        pass

    # Find inflection points (sign changes in slope)
    inflection_points: list[str] = []
    for feat, trend_data in trends.items():
        vals = trend_data["values"]
        for i in range(1, len(vals) - 1):
            if (vals[i] - vals[i-1]) * (vals[i+1] - vals[i]) < 0:
                inflection_points.append(f"{feat} at {time_labels[i]}")

    return {
        "trend_direction": overall,
        "feature_trends": trends,
        "inflection_points": inflection_points,
        "forecast": forecast,
    }
