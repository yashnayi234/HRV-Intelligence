"""Unit tests for HRVClinicalLoader."""

from __future__ import annotations

import sys
import os

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.loader import (
    ALL_COLS,
    ALL_FEATURE_COLS,
    HRVClinicalLoader,
)


@pytest.fixture
def loader() -> HRVClinicalLoader:
    return HRVClinicalLoader()


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Create a minimal valid DataFrame with all required columns."""
    n = 10
    data: dict[str, object] = {}
    for col in ALL_COLS:
        if col in ("SI > 1", "Sepsis3"):
            data[col] = [0] * 9 + [1]
        else:
            data[col] = [0.5] * n
    # Realistic physiological values
    data["Mean.rate"] = [75.0] * n
    data["Poincar..SD1"] = [0.03] * n
    data["Poincar..SD2"] = [0.05] * n
    data["LF.HF.ratio.LombScargle"] = [1.5] * n
    data["DFA.Alpha.1"] = [1.0] * n
    data["Multiscale.Entropy"] = [1.5] * n
    data["Complexity"] = [80.0] * n
    return pd.DataFrame(data)


def test_validate_schema_passes(loader: HRVClinicalLoader, sample_df: pd.DataFrame) -> None:
    result = loader.validate_schema(sample_df)
    assert result.valid, f"Schema should be valid. Missing: {result.missing_columns}"
    assert result.record_count == 10
    assert result.sepsis_count == 1
    assert abs(result.sepsis_prevalence - 0.1) < 0.01


def test_validate_schema_missing_column(
    loader: HRVClinicalLoader, sample_df: pd.DataFrame
) -> None:
    df = sample_df.drop(columns=["Poincar..SD1"])
    result = loader.validate_schema(df)
    assert not result.valid
    assert "Poincar..SD1" in result.missing_columns


def test_get_feature_groups(loader: HRVClinicalLoader) -> None:
    groups = loader.get_feature_groups()
    assert set(groups.keys()) == {
        "labels", "time_domain", "poincare", "frequency",
        "nonlinear", "entropy", "recurrence"
    }
    # All 59 columns accounted for
    all_in_groups = sum(len(v) for v in groups.values())
    assert all_in_groups == len(ALL_COLS)  # 59 including labels


def test_split_features_labels(
    loader: HRVClinicalLoader, sample_df: pd.DataFrame
) -> None:
    X, y_sepsis, y_si = loader.split_features_labels(sample_df)
    assert len(X) == 10
    assert len(y_sepsis) == 10
    assert len(y_si) == 10
    assert list(X.columns) == ALL_FEATURE_COLS
    assert "Sepsis3" not in X.columns
    assert "SI > 1" not in X.columns


def test_get_stats_summary(
    loader: HRVClinicalLoader, sample_df: pd.DataFrame
) -> None:
    stats = loader.get_stats_summary(sample_df)
    assert stats["n_records"] == 10
    assert stats["sepsis_count"] == 1
    assert "feature_stats" in stats
    assert "Mean.rate" in stats["feature_stats"]


def test_all_feature_cols_count() -> None:
    """Ensure exactly 57 feature columns (59 total - 2 labels)."""
    assert len(ALL_FEATURE_COLS) == 57
    assert len(ALL_COLS) == 59
