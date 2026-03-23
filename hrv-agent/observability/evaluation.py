"""ML metrics computation for the observability layer."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

_cached_metrics: dict[str, Any] | None = None
_metrics_path = os.getenv("METRICS_PATH", "ml/models/metrics.json")


def load_saved_metrics() -> dict[str, Any] | None:
    """Load saved model evaluation metrics from disk."""
    global _cached_metrics
    if _cached_metrics is not None:
        return _cached_metrics
    p = Path(_metrics_path)
    if p.exists():
        with open(p) as f:
            _cached_metrics = json.load(f)
    return _cached_metrics


def save_metrics(metrics: dict[str, Any]) -> None:
    """Persist evaluation metrics to disk."""
    global _cached_metrics
    _cached_metrics = metrics
    p = Path(_metrics_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(metrics, f, indent=2)
    logger.info("Metrics saved", path=str(p))
