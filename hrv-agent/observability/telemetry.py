"""Telemetry and cost tracking for the HRV agent pipeline."""

from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Any

from pydantic import BaseModel, Field


class NodeTelemetry(BaseModel):
    """Per-node execution telemetry."""

    node_name: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    bedrock_cost_usd: float = 0.0
    anomalies_detected: int = 0
    risk_levels_output: dict[str, int] = Field(default_factory=dict)


class PipelineTelemetry(BaseModel):
    """Full pipeline execution telemetry."""

    pipeline_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    total_latency_ms: float = 0.0
    total_cost_usd: float = 0.0
    records_processed: int = 0
    critical_cases_flagged: int = 0
    node_path_taken: list[str] = Field(default_factory=list)
    nodes: list[NodeTelemetry] = Field(default_factory=list)


# In-memory ring buffer of last 100 pipeline runs
_pipeline_history: deque[PipelineTelemetry] = deque(maxlen=100)


def record_pipeline_telemetry(
    state_metadata: dict[str, Any],
    records_processed: int,
    risk_levels: list[Any],
) -> PipelineTelemetry:
    """Extract telemetry from final agent state and store in history."""
    from data.models import RiskLevel

    critical_count = sum(1 for r in risk_levels if r == RiskLevel.CRITICAL)

    telem = PipelineTelemetry(
        total_latency_ms=state_metadata.get("total_latency_ms", 0.0),
        total_cost_usd=state_metadata.get("estimated_bedrock_cost_usd", 0.0),
        records_processed=records_processed,
        critical_cases_flagged=critical_count,
        node_path_taken=state_metadata.get("node_path", []),
    )

    _pipeline_history.append(telem)
    return telem


def get_pipeline_history(n: int = 100) -> list[dict[str, Any]]:
    """Return last N pipeline telemetry records."""
    items = list(_pipeline_history)[-n:]
    return [t.model_dump() for t in items]
