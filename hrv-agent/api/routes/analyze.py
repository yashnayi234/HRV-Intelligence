"""Analysis routes — /analyze/single and /analyze/batch."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends

from agents.graph import run_hrv_pipeline
from api.auth import verify_api_key
from data.models import (
    BatchAnalysisRequest,
    BatchAnalysisResult,
    HRVRecord,
    RiskLevel,
    SingleAnalysisResult,
)
from observability.telemetry import record_pipeline_telemetry

router = APIRouter(prefix="/analyze", tags=["Analysis"])


async def _analyze_records(
    records: list[HRVRecord],
    analysis_mode: str = "full",
) -> dict:
    """Run the pipeline and extract per-record results."""
    start = time.perf_counter()
    state = await run_hrv_pipeline(records, analysis_mode=analysis_mode)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Record telemetry
    record_pipeline_telemetry(
        state.get("processing_metadata", {}),
        records_processed=len(records),
        risk_levels=state.get("risk_levels", []),
    )

    return state, elapsed_ms


@router.post("/single", response_model=SingleAnalysisResult)
async def analyze_single(
    record: HRVRecord,
    _: str = Depends(verify_api_key),
) -> SingleAnalysisResult:
    """Analyze a single HRV record through the full agent pipeline."""
    state, elapsed_ms = await _analyze_records([record], "full")

    return SingleAnalysisResult(
        risk_level=state["risk_levels"][0] if state["risk_levels"] else RiskLevel.LOW,
        sepsis_probability=state["risk_scores"][0] if state["risk_scores"] else 0.0,
        anomalies=state.get("anomalies", []),
        clinical_interpretation=state.get("clinical_interpretation", ""),
        recommendations=state.get("recommendations", []),
        similar_cases=state.get("similar_cases", []),
        processing_ms=elapsed_ms,
    )


@router.post("/batch", response_model=BatchAnalysisResult)
async def analyze_batch(
    request: BatchAnalysisRequest,
    _: str = Depends(verify_api_key),
) -> BatchAnalysisResult:
    """Analyze a batch of HRV records."""
    state, elapsed_ms = await _analyze_records(request.records, request.analysis_mode)

    risk_levels = state.get("risk_levels", [])
    risk_scores = state.get("risk_scores", [])

    results = [
        SingleAnalysisResult(
            risk_level=risk_levels[i] if i < len(risk_levels) else RiskLevel.LOW,
            sepsis_probability=risk_scores[i] if i < len(risk_scores) else 0.0,
            anomalies=state.get("anomalies", []),
            clinical_interpretation=state.get("clinical_interpretation", ""),
            recommendations=state.get("recommendations", []),
            similar_cases=state.get("similar_cases", []),
            processing_ms=elapsed_ms,
        )
        for i in range(len(request.records))
    ]

    return BatchAnalysisResult(
        results=results,
        summary_stats=state.get("feature_summary", {}),
        critical_count=sum(1 for r in risk_levels if r == RiskLevel.CRITICAL),
        high_count=sum(1 for r in risk_levels if r == RiskLevel.HIGH),
        processing_ms=elapsed_ms,
    )
