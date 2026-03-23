"""ML risk scoring node — XGBoost inference for sepsis probability."""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import structlog

from agents.state import HRVAgentState
from data.loader import ALL_FEATURE_COLS
from data.models import HRVRecord, RiskLevel
from ml.classifier import HRVClassifier

logger = structlog.get_logger(__name__)

# Singleton classifier, loaded once
_classifier: HRVClassifier | None = None


def _get_classifier() -> HRVClassifier:
    global _classifier
    if _classifier is None:
        _classifier = HRVClassifier()
        model_path = os.getenv("MODEL_PATH", "ml/models/xgb_hrv_v1.pkl")
        try:
            _classifier.load_model(model_path)
        except FileNotFoundError:
            logger.warning(
                "Model file not found — using fallback risk scoring",
                model_path=model_path,
            )
    return _classifier


def _record_to_df(records: list[HRVRecord]) -> pd.DataFrame:
    """Convert list of HRVRecord to DataFrame using raw feature columns."""
    rows = []
    for rec in records:
        row = {col: None for col in ALL_FEATURE_COLS}
        # Map Pydantic model fields back to column names via aliases
        model_data = rec.model_dump(by_alias=True)
        for col in ALL_FEATURE_COLS:
            if col in model_data:
                row[col] = model_data[col]
        rows.append(row)
    return pd.DataFrame(rows)


async def ml_scoring_node(state: HRVAgentState) -> dict[str, Any]:
    """
    Runs XGBoost inference on all records to produce sepsis probability scores.

    Falls back to composite risk_score heuristic if model not loaded.
    """
    start = time.perf_counter()
    records: list[HRVRecord] = state["records"]

    clf = _get_classifier()

    risk_scores: list[float] = []
    risk_levels: list[RiskLevel] = []

    if clf._model is not None:
        X = _record_to_df(records)
        X_eng = clf._model.feature_engineer.transform(X)
        raw_probs = clf._model.classifier.predict_proba(
            X_eng[clf._model.feature_names]
        )[:, 1]
        composite_scores = X_eng["risk_score"].tolist() if "risk_score" in X_eng.columns else [0.0] * len(records)

        from ml.classifier import probability_to_risk_level
        for xgb_prob, composite in zip(raw_probs, composite_scores):
            # Blend: composite risk score floors the probability so high clinical
            # signals (elevated LF/HF, low MSE, collapsed SD1) always surface risk
            blended_prob = float(max(float(xgb_prob), float(composite) * 0.6))
            risk_scores.append(round(blended_prob, 4))
            risk_levels.append(probability_to_risk_level(blended_prob))
    else:
        # Fallback: deterministic heuristic risk scoring
        logger.warning("Using heuristic fallback for risk scoring")
        for rec in records:
            # Simplified weighted score
            lf_hf_n = min(rec.lf_hf_ratio / 10.0, 1.0)
            mse_n = 1.0 - min(rec.multiscale_entropy / 3.0, 1.0)
            sd1_n = 1.0 - min(rec.poincare_sd1 / 0.05, 1.0)
            score = 0.40 * lf_hf_n + 0.35 * mse_n + 0.25 * sd1_n
            score = max(0.0, min(1.0, score))
            risk_scores.append(score)
            from ml.classifier import probability_to_risk_level
            risk_levels.append(probability_to_risk_level(score))

    latency = (time.perf_counter() - start) * 1000
    metadata = state.get("processing_metadata", {})
    metadata.setdefault("node_path", []).append("ml_scoring_node")
    metadata["ml_scoring_latency_ms"] = latency
    metadata["critical_cases"] = sum(1 for r in risk_levels if r == RiskLevel.CRITICAL)

    logger.info(
        "ML scoring complete",
        n_records=len(records),
        critical_count=metadata["critical_cases"],
        mean_prob=f"{sum(risk_scores)/len(risk_scores):.3f}" if risk_scores else "N/A",
        latency_ms=f"{latency:.1f}",
    )

    return {
        "risk_scores": risk_scores,
        "risk_levels": risk_levels,
        "processing_metadata": metadata,
    }
