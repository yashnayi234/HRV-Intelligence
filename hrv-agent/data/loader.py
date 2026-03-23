"""HRV Clinical Data Loader — loads, validates, and prepares the dataset."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

# ── Column name groups matching the exact Excel sheet headers ─────────────────

LABEL_COLS: list[str] = ["SI > 1", "Sepsis3"]

TIME_DOMAIN_COLS: list[str] = [
    "Mean.rate",
    "Coefficient.of.variation",
    "mean",
    "median",
]

POINCARE_COLS: list[str] = [
    "Poincar..SD1",
    "Poincar..SD2",
]

FREQUENCY_COLS: list[str] = [
    "LF.HF.ratio.LombScargle",
    "LF.Power.LombScargle",
    "HF.Power.LombScargle",
    "VLF.Power.LombScargle",
    "Power.Law.Slope.LombScargle",
    "Power.Law.Y.Intercept.LombScargle",
]

NONLINEAR_COLS: list[str] = [
    "DFA.Alpha.1",
    "DFA.Alpha.2",
    "DFA.AUC",
    "Largest.Lyapunov.exponent",
    "Correlation.dimension",
    "Multiscale.Entropy",
    "Complexity",
    "Hurst.exponent",
]

ENTROPY_COLS: list[str] = [
    "shannEn",
    "QSE",
    "KLPE",
]

RECURRENCE_COLS: list[str] = [
    "SymDp0_2", "SymDp1_2", "SymDp2_2", "SymDfw_2", "SymDse_2", "SymDce_2",
    "eScaleE", "pR", "pD", "dlmax", "sedl", "pDpR", "pL", "vlmax", "sevl",
    "PSeo", "Teo", "formF", "gcount", "sgridAND", "sgridTAU", "sgridWGT",
    "aFdP", "fFdP", "IoV", "AsymI", "CSI", "CVI", "ARerr", "histSI",
    "MultiFractal_c1", "MultiFractal_c2", "SDLEalpha", "SDLEmean",
]

ALL_FEATURE_COLS: list[str] = (
    TIME_DOMAIN_COLS + POINCARE_COLS + FREQUENCY_COLS +
    NONLINEAR_COLS + ENTROPY_COLS + RECURRENCE_COLS
)

ALL_COLS: list[str] = LABEL_COLS + ALL_FEATURE_COLS


@dataclass
class ValidationResult:
    """Schema validation outcome."""

    valid: bool
    missing_columns: list[str]
    extra_columns: list[str]
    null_counts: dict[str, int]
    record_count: int
    sepsis_count: int
    sepsis_prevalence: float

    def __str__(self) -> str:
        return (
            f"ValidationResult(valid={self.valid}, records={self.record_count}, "
            f"missing={self.missing_columns}, nulls={sum(self.null_counts.values())}, "
            f"sepsis_prevalence={self.sepsis_prevalence:.1%})"
        )


class HRVClinicalLoader:
    """
    Loads and validates the clinical HRV dataset.

    Dataset: HRV_data_20201209_2.xlsx
    Sheet:   hrvtotalnorepeat+fea20200508_12
    Records: 4,314 patient observations
    Features: 59 columns (labels + HRV biomarkers)
    """

    SHEET_NAME = "hrvtotalnorepeat+fea20200508_12"
    EXPECTED_RECORDS = 4314
    EXPECTED_COLS = 59

    def load_from_xlsx(self, path: str) -> pd.DataFrame:
        """Load the HRV dataset from the Excel file."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Dataset not found at {path}")

        logger.info("Loading HRV dataset", path=str(p))
        df = pd.read_excel(p, sheet_name=self.SHEET_NAME, engine="openpyxl")

        logger.info(
            "Dataset loaded",
            records=len(df),
            columns=len(df.columns),
        )
        return df

    def validate_schema(self, df: pd.DataFrame) -> ValidationResult:
        """Validate that all 59 expected columns are present and dataset is clean."""
        df_cols = set(df.columns.tolist())
        expected = set(ALL_COLS)

        missing = sorted(expected - df_cols)
        extra = sorted(df_cols - expected)
        null_counts = {col: int(df[col].isna().sum()) for col in ALL_COLS if col in df_cols}
        sepsis_count = int(df["Sepsis3"].sum()) if "Sepsis3" in df_cols else 0
        record_count = len(df)
        sepsis_prevalence = sepsis_count / record_count if record_count > 0 else 0.0

        valid = (
            len(missing) == 0
            and sum(null_counts.values()) == 0
        )

        result = ValidationResult(
            valid=valid,
            missing_columns=missing,
            extra_columns=extra,
            null_counts={k: v for k, v in null_counts.items() if v > 0},
            record_count=record_count,
            sepsis_count=sepsis_count,
            sepsis_prevalence=sepsis_prevalence,
        )
        logger.info("Schema validation", result=str(result))
        return result

    def get_feature_groups(self) -> dict[str, list[str]]:
        """Return feature groups keyed by group name."""
        return {
            "labels": LABEL_COLS,
            "time_domain": TIME_DOMAIN_COLS,
            "poincare": POINCARE_COLS,
            "frequency": FREQUENCY_COLS,
            "nonlinear": NONLINEAR_COLS,
            "entropy": ENTROPY_COLS,
            "recurrence": RECURRENCE_COLS,
        }

    def split_features_labels(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """Split DataFrame into features X, primary label y_sepsis, secondary label y_si."""
        X = df[ALL_FEATURE_COLS].copy()
        y_sepsis = df["Sepsis3"].copy()
        y_si = df["SI > 1"].copy()
        return X, y_sepsis, y_si

    def get_stats_summary(self, df: pd.DataFrame) -> dict[str, Any]:
        """Compute descriptive statistics and class distribution."""
        X, y_sepsis, _ = self.split_features_labels(df)

        stats: dict[str, Any] = {
            "n_records": len(df),
            "n_features": len(ALL_FEATURE_COLS),
            "sepsis_count": int(y_sepsis.sum()),
            "no_sepsis_count": int((y_sepsis == 0).sum()),
            "sepsis_prevalence": float(y_sepsis.mean()),
            "feature_stats": {},
        }

        for col in ALL_FEATURE_COLS:
            if col in df.columns:
                col_data = df[col].dropna()
                stats["feature_stats"][col] = {
                    "mean": float(col_data.mean()),
                    "std": float(col_data.std()),
                    "min": float(col_data.min()),
                    "max": float(col_data.max()),
                    "median": float(col_data.median()),
                    "sepsis_mean": float(df.loc[df["Sepsis3"] == 1, col].mean()),
                    "no_sepsis_mean": float(df.loc[df["Sepsis3"] == 0, col].mean()),
                }

        return stats

    def get_training_distribution(
        self, df: pd.DataFrame
    ) -> dict[str, dict[str, float]]:
        """Compute per-feature mean and std for outlier detection (Z-score gating)."""
        X, _, _ = self.split_features_labels(df)
        return {
            col: {"mean": float(X[col].mean()), "std": float(X[col].std())}
            for col in ALL_FEATURE_COLS
        }
