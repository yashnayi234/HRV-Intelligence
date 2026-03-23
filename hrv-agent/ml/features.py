"""Feature engineering for HRV sepsis risk classification."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from data.loader import ALL_FEATURE_COLS


class HRVFeatureEngineer:
    """
    Computes engineered features on top of the 55 raw HRV features.

    Composite risk score uses clinically-weighted combination of key biomarkers.
    Interaction features capture non-additive relationships between domains.
    """

    def __init__(self) -> None:
        self._scaler: MinMaxScaler | None = None

    def fit(self, X: pd.DataFrame) -> "HRVFeatureEngineer":
        """Fit MinMaxScaler on training data."""
        self._scaler = MinMaxScaler()
        self._scaler.fit(X[ALL_FEATURE_COLS])
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Add engineered features. Requires fit() to have been called."""
        if self._scaler is None:
            raise RuntimeError("Call fit() before transform()")

        out = X.copy()
        scaled = self._scaler.transform(X[ALL_FEATURE_COLS])
        scaled_df = pd.DataFrame(scaled, columns=ALL_FEATURE_COLS, index=X.index)

        # ── Composite risk score ─────────────────────────────────────────────
        # Deviation of DFA alpha1 from 1.0 (healthy reference), scaled 0-1
        dfa_deviation = scaled_df["DFA.Alpha.1"].sub(
            self._scaler.transform(
                pd.DataFrame({"DFA.Alpha.1": [1.0]}, index=[0])
                .reindex(columns=ALL_FEATURE_COLS, fill_value=0)
            )[0, ALL_FEATURE_COLS.index("DFA.Alpha.1")]
        ).abs()

        out["risk_score"] = (
            0.20 * scaled_df["LF.HF.ratio.LombScargle"]
            + 0.20 * (1.0 - scaled_df["Multiscale.Entropy"])
            + 0.15 * dfa_deviation
            + 0.15 * (1.0 - scaled_df["Poincar..SD1"])
            + 0.15 * (1.0 - scaled_df["Complexity"])
            + 0.15 * scaled_df["Mean.rate"]
        ).clip(0.0, 1.0)

        # ── Interaction features ─────────────────────────────────────────────
        # SD1/SD2 ratio: captures Poincaré ellipse shape
        out["sd1_sd2_ratio"] = (
            X["Poincar..SD1"] / (X["Poincar..SD2"] + 1e-9)
        )

        # LF power × DFA alpha1: frequency + fractal joint signal
        out["lf_dfa_interaction"] = (
            X["LF.Power.LombScargle"] * X["DFA.Alpha.1"]
        )

        # Entropy-complexity product: both collapsing together is a strong signal
        out["entropy_complexity_product"] = (
            X["Multiscale.Entropy"] * X["Complexity"]
        )

        # Sympathetic load index: LF/HF × mean heart rate
        out["sympathetic_load"] = (
            X["LF.HF.ratio.LombScargle"] * X["Mean.rate"]
        )

        return out

    def fit_transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return self.fit(X).transform(X)

    @property
    def engineered_feature_names(self) -> list[str]:
        return [
            "risk_score",
            "sd1_sd2_ratio",
            "lf_dfa_interaction",
            "entropy_complexity_product",
            "sympathetic_load",
        ]

    @property
    def all_feature_names(self) -> list[str]:
        return ALL_FEATURE_COLS + self.engineered_feature_names
