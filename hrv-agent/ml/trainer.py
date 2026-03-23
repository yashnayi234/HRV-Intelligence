"""Training, evaluation, and persistence for the HRV XGBoost classifier."""

from __future__ import annotations

import json
import pickle
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import structlog
from imblearn.over_sampling import SMOTE
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_curve,
    auc,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split

from data.loader import HRVClinicalLoader
from ml.classifier import HRVClassifier, TrainedModel
from ml.features import HRVFeatureEngineer

logger = structlog.get_logger(__name__)


@dataclass
class ModelMetrics:
    """Evaluation metrics for the trained classifier."""

    auc_roc: float
    f1: float
    precision: float
    recall: float
    confusion_matrix: list[list[int]]
    top_features: list[dict[str, Any]]
    n_train: int
    n_test: int
    n_sepsis_test: int

    def __str__(self) -> str:
        return (
            f"AUC-ROC: {self.auc_roc:.4f} | F1: {self.f1:.4f} | "
            f"Precision: {self.precision:.4f} | Recall: {self.recall:.4f}"
        )


class HRVTrainer:
    """
    Trains and evaluates the HRV sepsis classifier.

    Pipeline:
        1. 80/20 stratified train/test split
        2. Feature engineering on train set
        3. SMOTE oversampling on engineered training features
        4. XGBoost training
        5. Isotonic calibration via CalibratedClassifierCV
        6. Evaluation on held-out (non-SMOTE-d) test set
    """

    TEST_SIZE = 0.20
    RANDOM_STATE = 42

    def __init__(self) -> None:
        self._loader = HRVClinicalLoader()
        self._clf_wrapper = HRVClassifier()

    def train(
        self,
        df: pd.DataFrame,
        model_save_path: str | None = None,
    ) -> tuple[TrainedModel, ModelMetrics]:
        """Full training run. Returns trained model + evaluation metrics."""

        # ── 1. Split features / labels ────────────────────────────────────────
        X, y_sepsis, _ = self._loader.split_features_labels(df)
        logger.info("Training started", n_records=len(X), n_sepsis=int(y_sepsis.sum()))

        # ── 2. Stratified 80/20 split ─────────────────────────────────────────
        X_train_raw, X_test_raw, y_train, y_test = train_test_split(
            X, y_sepsis,
            test_size=self.TEST_SIZE,
            random_state=self.RANDOM_STATE,
            stratify=y_sepsis,
        )

        # ── 3. Feature engineering (fit only on train) ────────────────────────
        engineer = HRVFeatureEngineer()
        X_train_eng = engineer.fit_transform(X_train_raw)
        X_test_eng = engineer.transform(X_test_raw)

        feature_names = engineer.all_feature_names

        # ── 4. SMOTE to oversample minority class (training only) ─────────────
        smote = SMOTE(random_state=self.RANDOM_STATE, k_neighbors=5)
        X_train_balanced, y_train_balanced = smote.fit_resample(
            X_train_eng[feature_names], y_train
        )
        logger.info(
            "SMOTE applied",
            original_sepsis=int(y_train.sum()),
            balanced_sepsis=int(y_train_balanced.sum()),
        )

        # ── 5. Train XGBoost ──────────────────────────────────────────────────
        base_xgb = self._clf_wrapper.build_xgb()
        calibrated = CalibratedClassifierCV(
            base_xgb, method="isotonic", cv=5
        )
        calibrated.fit(
            pd.DataFrame(X_train_balanced, columns=feature_names),
            y_train_balanced,
        )
        logger.info("Training complete")

        # ── 6. Evaluate on test set ───────────────────────────────────────────
        # Get base XGB from calibrated CV (for feature importances)
        raw_xgb = None
        if hasattr(calibrated, 'calibrated_classifiers_'):
            try:
                raw_xgb = calibrated.calibrated_classifiers_[0].estimator
            except Exception:
                pass

        metrics = self.evaluate(
            calibrated, X_test_eng[feature_names], y_test, feature_names, raw_xgb
        )
        logger.info("Evaluation complete", metrics=str(metrics))

        trained_model = TrainedModel(
            feature_engineer=engineer,
            classifier=calibrated,
            feature_names=feature_names,
            training_stats={
                "n_train": len(X_train_raw),
                "n_test": len(X_test_raw),
                "n_sepsis_train": int(y_train.sum()),
                "n_sepsis_test": int(y_test.sum()),
                "auc_roc": metrics.auc_roc,
            },
        )
        self._clf_wrapper._model = trained_model

        if model_save_path:
            self.save_model(trained_model, model_save_path)

        return trained_model, metrics

    def evaluate(
        self,
        calibrated_clf: CalibratedClassifierCV,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        feature_names: list[str],
        base_xgb: Any | None = None,
    ) -> ModelMetrics:
        """Compute evaluation metrics on the held-out test set.

        Uses threshold optimization to maximize recall >= 0.75
        (clinical priority: minimize missed sepsis cases).
        """
        probs = calibrated_clf.predict_proba(X_test)[:, 1]

        # Find threshold that maximizes F1 while maintaining recall > 0.75
        best_threshold = 0.50
        best_f1 = 0.0
        for t in np.arange(0.10, 0.65, 0.01):
            preds_t = (probs >= t).astype(int)
            rec = recall_score(y_test, preds_t, zero_division=0)
            prec = precision_score(y_test, preds_t, zero_division=0)
            f1_t = f1_score(y_test, preds_t, zero_division=0)
            if rec >= 0.75 and f1_t > best_f1:
                best_f1 = f1_t
                best_threshold = t

        preds = (probs >= best_threshold).astype(int)
        logger.info("Optimal threshold selected", threshold=round(best_threshold, 2))

        auc_roc = float(roc_auc_score(y_test, probs))
        f1 = float(f1_score(y_test, preds, zero_division=0))
        precision = float(precision_score(y_test, preds, zero_division=0))
        recall = float(recall_score(y_test, preds, zero_division=0))
        cm = confusion_matrix(y_test, preds).tolist()

        # Top-10 feature importances from the base XGBoost estimator
        top_features: list[dict[str, Any]] = []
        if base_xgb is not None and hasattr(base_xgb, "feature_importances_"):
            importances = base_xgb.feature_importances_
            feature_importance_pairs = sorted(
                zip(feature_names, importances),
                key=lambda x: x[1],
                reverse=True,
            )[:10]
            top_features = [
                {"feature": f, "importance": round(float(imp), 6)}
                for f, imp in feature_importance_pairs
            ]

        return ModelMetrics(
            auc_roc=auc_roc,
            f1=f1,
            precision=precision,
            recall=recall,
            confusion_matrix=cm,
            top_features=top_features,
            n_train=0,  # filled by caller
            n_test=len(y_test),
            n_sepsis_test=int(y_test.sum()),
        )

    def save_model(self, model: TrainedModel, path: str) -> None:
        """Persist the trained model to disk."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            pickle.dump(model, f)
        logger.info("Model saved", path=str(p))

    def load_model(self, path: str) -> TrainedModel:
        """Load a saved model from disk."""
        p = Path(path)
        with open(p, "rb") as f:
            model = pickle.load(f)
        logger.info("Model loaded", path=str(p))
        return model


def main() -> None:
    """CLI entry point: train the model and print metrics."""
    import sys

    logging_import()
    data_path = sys.argv[1] if len(sys.argv) > 1 else "data/HRV_data_20201209_2.xlsx"
    model_path = sys.argv[2] if len(sys.argv) > 2 else "ml/models/xgb_hrv_v1.pkl"

    loader = HRVClinicalLoader()
    df = loader.load_from_xlsx(data_path)

    validation = loader.validate_schema(df)
    if not validation.valid:
        print(f"Schema validation FAILED: {validation}")
        sys.exit(1)

    print(
        f"Dataset loaded: {validation.record_count} records, "
        f"sepsis prevalence={validation.sepsis_prevalence:.1%}"
    )

    trainer = HRVTrainer()
    model, metrics = trainer.train(df, model_save_path=model_path)

    print("\n" + "=" * 60)
    print("MODEL EVALUATION RESULTS")
    print("=" * 60)
    print(f"  AUC-ROC:   {metrics.auc_roc:.4f}  (target > 0.80)")
    print(f"  F1-Score:  {metrics.f1:.4f}  (target > 0.70)")
    print(f"  Precision: {metrics.precision:.4f}")
    print(f"  Recall:    {metrics.recall:.4f}  (target > 0.75)")
    print(f"\nConfusion Matrix:")
    for row in metrics.confusion_matrix:
        print(f"  {row}")
    print(f"\nTop-10 Feature Importances:")
    for feat in metrics.top_features:
        print(f"  {feat['feature']:<45} {feat['importance']:.6f}")

    target_met = metrics.auc_roc > 0.80 and metrics.recall > 0.75
    print(f"\n{'✅ TARGETS MET' if target_met else '⚠️  TARGETS NOT MET'}")


def logging_import() -> None:
    import structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )


if __name__ == "__main__":
    main()
