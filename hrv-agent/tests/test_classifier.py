"""Tests for ML classifier feature engineering."""

from __future__ import annotations

import sys
import os

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.loader import ALL_FEATURE_COLS
from ml.features import HRVFeatureEngineer


@pytest.fixture
def sample_features() -> pd.DataFrame:
    n = 50
    data = {col: np.random.uniform(0.0, 1.0, n) for col in ALL_FEATURE_COLS}
    data["Mean.rate"] = np.random.uniform(60, 100, n)
    data["Poincar..SD1"] = np.random.uniform(0.01, 0.05, n)
    data["Poincar..SD2"] = np.random.uniform(0.02, 0.1, n)
    data["LF.HF.ratio.LombScargle"] = np.random.uniform(0.5, 5.0, n)
    data["DFA.Alpha.1"] = np.random.uniform(0.5, 1.5, n)
    data["Multiscale.Entropy"] = np.random.uniform(0.5, 2.5, n)
    data["Complexity"] = np.random.uniform(30, 150, n)
    return pd.DataFrame(data)


def test_feature_engineer_adds_columns(sample_features: pd.DataFrame) -> None:
    """fit_transform should add 5 engineered features."""
    engineer = HRVFeatureEngineer()
    out = engineer.fit_transform(sample_features)

    for feat in engineer.engineered_feature_names:
        assert feat in out.columns, f"Missing feature: {feat}"


def test_risk_score_bounded(sample_features: pd.DataFrame) -> None:
    """risk_score should always be in [0, 1]."""
    engineer = HRVFeatureEngineer()
    out = engineer.fit_transform(sample_features)
    assert out["risk_score"].between(0.0, 1.0).all(), "risk_score out of [0, 1]"


def test_transform_requires_fit(sample_features: pd.DataFrame) -> None:
    """transform() without fit() should raise RuntimeError."""
    engineer = HRVFeatureEngineer()
    with pytest.raises(RuntimeError, match="Call fit\\(\\)"):
        engineer.transform(sample_features)


def test_all_feature_names_count(sample_features: pd.DataFrame) -> None:
    """Total feature count = 57 raw + 5 engineered = 62."""
    engineer = HRVFeatureEngineer()
    assert len(engineer.all_feature_names) == 57 + 5


def test_sd1_sd2_ratio_positive(sample_features: pd.DataFrame) -> None:
    """sd1_sd2_ratio should always be positive."""
    engineer = HRVFeatureEngineer()
    out = engineer.fit_transform(sample_features)
    assert (out["sd1_sd2_ratio"] > 0).all()
