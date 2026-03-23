"""XGBoost sepsis risk classifier with calibration and risk stratification."""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from sklearn.calibration import CalibratedClassifierCV

import xgboost as xgb

from data.models import RiskLevel
from ml.features import HRVFeatureEngineer

logger = structlog.get_logger(__name__)


@dataclass
class PredictionResult:
    """Output for a single record prediction."""

    sepsis_probability: float
    risk_level: RiskLevel
    risk_score: float


@dataclass
class TrainedModel:
    """Container for the trained classifier pipeline."""

    feature_engineer: HRVFeatureEngineer
    classifier: CalibratedClassifierCV
    feature_names: list[str]
    training_stats: dict[str, Any]


def probability_to_risk_level(prob: float) -> RiskLevel:
    """Map sepsis probability to a clinical risk tier."""
    if prob < 0.25:
        return RiskLevel.LOW
    elif prob < 0.50:
        return RiskLevel.MODERATE
    elif prob < 0.75:
        return RiskLevel.HIGH
    else:
        return RiskLevel.CRITICAL


class HRVClassifier:
    """
    Hybrid XGBoost classifier for sepsis risk prediction.

    Pipeline:
        1. Feature engineering (composite risk score + interactions)
        2. XGBoost base classifier (scale_pos_weight handles class imbalance)
        3. Isotonic calibration for reliable probability outputs
    """

    # Class imbalance: ~7.0 ratio (87.5% non-sepsis / 12.5% sepsis)
    SCALE_POS_WEIGHT = 7.0

    def __init__(self) -> None:
        self._model: TrainedModel | None = None

    def build_xgb(self) -> xgb.XGBClassifier:
        """Instantiate the base XGBoost estimator."""
        return xgb.XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=self.SCALE_POS_WEIGHT,
            objective="binary:logistic",
            eval_metric="auc",
            random_state=42,
            n_jobs=-1,
            tree_method="hist",
        )

    def predict_single(self, record_features: pd.DataFrame) -> PredictionResult:
        """Predict sepsis risk for a single record."""
        if self._model is None:
            raise RuntimeError("No model loaded. Call load_model() or train first.")

        X_eng = self._model.feature_engineer.transform(record_features)

        prob = float(
            self._model.classifier.predict_proba(
                X_eng[self._model.feature_names]
            )[0, 1]
        )
        risk_score = float(X_eng["risk_score"].iloc[0]) if "risk_score" in X_eng.columns else prob
        return PredictionResult(
            sepsis_probability=prob,
            risk_level=probability_to_risk_level(prob),
            risk_score=risk_score,
        )

    def predict_batch(
        self, features: pd.DataFrame
    ) -> list[PredictionResult]:
        """Predict sepsis risk for a batch of records."""
        if self._model is None:
            raise RuntimeError("No model loaded.")

        X_eng = self._model.feature_engineer.transform(features)
        probs = self._model.classifier.predict_proba(
            X_eng[self._model.feature_names]
        )[:, 1]

        results = []
        for i, prob in enumerate(probs):
            risk_score = float(X_eng["risk_score"].iloc[i]) if "risk_score" in X_eng.columns else float(prob)
            results.append(
                PredictionResult(
                    sepsis_probability=float(prob),
                    risk_level=probability_to_risk_level(float(prob)),
                    risk_score=risk_score,
                )
            )
        return results

    def load_model(self, path: str) -> None:
        """Load a previously saved TrainedModel."""
        p = Path(path)
        with open(p, "rb") as f:
            self._model = pickle.load(f)
        logger.info("Model loaded", path=str(p))

    @property
    def model(self) -> TrainedModel:
        if self._model is None:
            raise RuntimeError("No model loaded.")
        return self._model
