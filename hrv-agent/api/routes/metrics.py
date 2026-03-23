"""Metrics and health check routes."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends

from api.auth import verify_api_key
from observability.evaluation import load_saved_metrics
from observability.telemetry import get_pipeline_history

router = APIRouter(tags=["Observability"])


@router.get("/model/metrics")
async def get_model_metrics(
    _: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Return ML model evaluation metrics from last training run."""
    metrics = load_saved_metrics()
    if metrics is None:
        return {"error": "No model metrics found. Run ml/trainer.py first."}
    return metrics


@router.get("/metrics")
async def get_pipeline_metrics(
    _: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """Return last 100 pipeline execution telemetry records."""
    history = get_pipeline_history(100)
    return {
        "pipeline_runs": len(history),
        "history": history,
    }


@router.get("/similar/{record_id}")
async def get_similar_cases(
    record_id: str,
    k: int = 5,
    _: str = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """Retrieve similar HRV cases from LanceDB by record ID."""
    try:
        from data.vector_store import HRVVectorStore
        store = HRVVectorStore()
        if store.is_ready():
            return store.get_similar_cases(record_id, k=k)
        return []
    except Exception as exc:
        return [{"error": str(exc)}]


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """System health check — Bedrock, LanceDB, and model status."""
    bedrock_ok = False
    lancedb_ok = False
    model_ok = False

    try:
        import boto3
        boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )
        bedrock_ok = True
    except Exception:
        pass

    try:
        from data.vector_store import HRVVectorStore
        store = HRVVectorStore()
        lancedb_ok = store.is_ready()
    except Exception:
        pass

    try:
        from ml.classifier import HRVClassifier
        clf = HRVClassifier()
        model_path = os.getenv("MODEL_PATH", "ml/models/xgb_hrv_v1.pkl")
        clf.load_model(model_path)
        model_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if (bedrock_ok and model_ok) else "degraded",
        "bedrock_connected": bedrock_ok,
        "lancedb_connected": lancedb_ok,
        "model_loaded": model_ok,
    }
