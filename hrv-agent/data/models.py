"""Pydantic v2 data models for HRV Agentic Intelligence System."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RiskLevel(str, Enum):
    """Sepsis risk stratification levels."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class HRVRecord(BaseModel):
    """Full 59-feature HRV patient record. All fields required (no nulls in dataset)."""

    # ── Labels ────────────────────────────────────────────────────────────────
    si_above_1: int = Field(..., alias="SI > 1", ge=0, le=1)
    sepsis3: int = Field(..., alias="Sepsis3", ge=0, le=1)

    # ── Time-domain ───────────────────────────────────────────────────────────
    mean_rate: float = Field(..., alias="Mean.rate", gt=0)
    coefficient_of_variation: float = Field(..., alias="Coefficient.of.variation")
    mean: float = Field(..., alias="mean")
    median: float = Field(..., alias="median")

    # ── Poincaré ──────────────────────────────────────────────────────────────
    poincare_sd1: float = Field(..., alias="Poincar..SD1")
    poincare_sd2: float = Field(..., alias="Poincar..SD2")

    # ── Frequency domain (LombScargle) ────────────────────────────────────────
    lf_hf_ratio: float = Field(..., alias="LF.HF.ratio.LombScargle")
    lf_power: float = Field(..., alias="LF.Power.LombScargle")
    hf_power: float = Field(..., alias="HF.Power.LombScargle")
    vlf_power: float = Field(..., alias="VLF.Power.LombScargle")
    power_law_slope: float = Field(..., alias="Power.Law.Slope.LombScargle")
    power_law_y_intercept: float = Field(..., alias="Power.Law.Y.Intercept.LombScargle")

    # ── Nonlinear / Fractal / Chaos ───────────────────────────────────────────
    dfa_alpha1: float = Field(..., alias="DFA.Alpha.1")
    dfa_alpha2: float = Field(..., alias="DFA.Alpha.2")
    dfa_auc: float = Field(..., alias="DFA.AUC")
    largest_lyapunov_exponent: float = Field(..., alias="Largest.Lyapunov.exponent")
    correlation_dimension: float = Field(..., alias="Correlation.dimension")
    multiscale_entropy: float = Field(..., alias="Multiscale.Entropy")
    complexity: float = Field(..., alias="Complexity")
    hurst_exponent: float = Field(..., alias="Hurst.exponent")

    # ── Entropy ───────────────────────────────────────────────────────────────
    shann_en: float = Field(..., alias="shannEn")
    qse: float = Field(..., alias="QSE")
    klpe: float = Field(..., alias="KLPE")

    # ── Recurrence / Symbolic dynamics ────────────────────────────────────────
    sym_dp0_2: float = Field(..., alias="SymDp0_2")
    sym_dp1_2: float = Field(..., alias="SymDp1_2")
    sym_dp2_2: float = Field(..., alias="SymDp2_2")
    sym_dfw_2: float = Field(..., alias="SymDfw_2")
    sym_dse_2: float = Field(..., alias="SymDse_2")
    sym_dce_2: float = Field(..., alias="SymDce_2")
    e_scale_e: float = Field(..., alias="eScaleE")
    p_r: float = Field(..., alias="pR")
    p_d: float = Field(..., alias="pD")
    dl_max: float = Field(..., alias="dlmax")
    sedl: float = Field(..., alias="sedl")
    p_dp_r: float = Field(..., alias="pDpR")
    p_l: float = Field(..., alias="pL")
    vl_max: float = Field(..., alias="vlmax")
    sevl: float = Field(..., alias="sevl")
    p_seo: float = Field(..., alias="PSeo")
    teo: float = Field(..., alias="Teo")
    form_f: float = Field(..., alias="formF")
    gcount: float = Field(..., alias="gcount")
    sgrid_and: float = Field(..., alias="sgridAND")
    sgrid_tau: float = Field(..., alias="sgridTAU")
    sgrid_wgt: float = Field(..., alias="sgridWGT")
    a_fd_p: float = Field(..., alias="aFdP")
    f_fd_p: float = Field(..., alias="fFdP")
    iov: float = Field(..., alias="IoV")
    asym_i: float = Field(..., alias="AsymI")
    csi: float = Field(..., alias="CSI")
    cvi: float = Field(..., alias="CVI")
    ar_err: float = Field(..., alias="ARerr")
    hist_si: float = Field(..., alias="histSI")
    multi_fractal_c1: float = Field(..., alias="MultiFractal_c1")
    multi_fractal_c2: float = Field(..., alias="MultiFractal_c2")
    sdle_alpha: float = Field(..., alias="SDLEalpha")
    sdle_mean: float = Field(..., alias="SDLEmean")

    @field_validator("mean_rate")
    @classmethod
    def validate_heart_rate(cls, v: float) -> float:
        if not (20 <= v <= 300):
            raise ValueError(f"Heart rate {v} bpm is physiologically implausible")
        return v

    model_config = {"populate_by_name": True}


class BatchAnalysisRequest(BaseModel):
    """Request model for batch HRV analysis."""

    records: list[HRVRecord]
    analysis_mode: Literal["quick", "full", "clinical"] = "full"


class AnomalyEvent(BaseModel):
    """A detected clinical anomaly in an HRV record."""

    feature: str
    value: float
    threshold: float
    severity: Literal["warning", "high", "critical"]
    clinical_description: str


class SingleAnalysisResult(BaseModel):
    """Result of analyzing a single HRV record."""

    risk_level: RiskLevel
    sepsis_probability: float = Field(..., ge=0.0, le=1.0)
    anomalies: list[AnomalyEvent]
    clinical_interpretation: str
    recommendations: list[str]
    similar_cases: list[dict]
    processing_ms: float


class BatchAnalysisResult(BaseModel):
    """Result of analyzing a batch of HRV records."""

    results: list[SingleAnalysisResult]
    summary_stats: dict
    critical_count: int
    high_count: int
    processing_ms: float


class ChatRequest(BaseModel):
    """Multi-turn conversational coach request."""

    message: str
    context_records: list[HRVRecord] | None = None


class ChatResponse(BaseModel):
    """Response from conversational coach."""

    reply: str
    sources: list[dict]


class ModelMetrics(BaseModel):
    """ML model evaluation metrics."""

    auc_roc: float
    f1: float
    precision: float
    recall: float
    confusion_matrix: list[list[int]]
    top_features: list[dict]
    training_date: str
