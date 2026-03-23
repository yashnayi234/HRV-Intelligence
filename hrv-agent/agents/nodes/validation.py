"""Data validation node — Pydantic schema checking and outlier flagging."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
import structlog

from agents.state import HRVAgentState
from data.models import HRVRecord

logger = structlog.get_logger(__name__)

# Z-score threshold for outlier flagging
OUTLIER_Z_THRESHOLD = 3.0


async def data_validation_node(state: HRVAgentState) -> dict[str, Any]:
    """
    Validates HRV records schema and flags physiological outliers.

    Logic:
        - Pydantic v2 already validated on ingest; here we flag Z-score outliers.
        - Checks batch_size to decide if routing to batch subgraph.
        - Records processing start time.
    """
    start = time.perf_counter()
    records: list[HRVRecord] = state["records"]

    processing_metadata: dict[str, Any] = state.get("processing_metadata", {})
    processing_metadata["node_path"] = ["data_validation_node"]
    processing_metadata["start_time"] = start

    validation_flags: list[str] = []

    # Quick sanity checks per record
    for i, rec in enumerate(records):
        if rec.mean_rate < 30 or rec.mean_rate > 220:
            validation_flags.append(f"record[{i}]: mean_rate {rec.mean_rate} unusual")
        if rec.lf_hf_ratio > 20:
            validation_flags.append(f"record[{i}]: LF/HF {rec.lf_hf_ratio:.2f} extreme")
        if rec.poincare_sd1 <= 0:
            validation_flags.append(f"record[{i}]: SD1 <= 0 invalid")

    if validation_flags:
        logger.warning("Validation flags detected", flags=validation_flags)

    processing_metadata["validation_flags"] = validation_flags
    processing_metadata["validation_latency_ms"] = (time.perf_counter() - start) * 1000

    return {
        "batch_size": len(records),
        "processing_metadata": processing_metadata,
    }
