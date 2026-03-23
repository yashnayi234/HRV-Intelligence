# HRV Agentic Intelligence System

> **Production-grade multi-agent AI system for clinical HRV analysis and early sepsis detection.**  
> Built with LangGraph · AWS Bedrock (Claude Sonnet 4) · XGBoost · FastAPI · React

---

## Table of Contents

1. [Overview](#overview)
2. [Why HRV?](#why-hrv)
3. [System Architecture](#system-architecture)
4. [Project Structure](#project-structure)
5. [Quick Start](#quick-start)
6. [ML Model](#ml-model)
7. [Agent Pipeline](#agent-pipeline)
8. [API Reference](#api-reference)
9. [Frontend Dashboard](#frontend-dashboard)
10. [AWS Bedrock Configuration](#aws-bedrock-configuration)
11. [Running Tests](#running-tests)
12. [Deployment](#deployment)
13. [Performance Results](#performance-results)

---

## Overview

The HRV Agentic Intelligence System ingests clinical Heart Rate Variability (HRV) data from ICU patients and runs a multi-agent LangGraph pipeline to:

- **Detect anomalies** in 59 HRV biomarkers
- **Classify sepsis risk** using a calibrated XGBoost model (AUC-ROC = 0.9311)
- **Generate clinical explanations** using Claude Sonnet 4 via AWS Bedrock
- **Produce prioritized recommendations** appropriate to the risk level
- **Expose results** via a FastAPI REST service with a React dashboard

This project is designed as a production-quality portfolio demonstrating the intersection of clinical HRV science, agentic AI engineering, and MLOps.

---

## Why HRV?

Heart Rate Variability is the variation in time between successive heartbeats. A healthy heart does **not** beat like a metronome — that variability reflects the autonomic nervous system's adaptive capacity.

| HRV Signal | Clinical Meaning |
|---|---|
| Low RMSSD / SD1 | Parasympathetic withdrawal — physiological stress |
| High LF/HF ratio (> 3) | Sympathetic dominance — fight-or-flight overactivated |
| Low DFA α1 (< 0.5) | Loss of fractal complexity — early organ dysfunction |
| Low Multiscale Entropy | Biological rigidity — sepsis signature |

**Sepsis kills ~270,000 Americans/year.** HRV drops measurably **12–24 hours before** clinical deterioration — making it a powerful early warning signal. This system uses 59 biomarkers across 5 HRV domains to detect that window.

---

## System Architecture

```
     ┌──────────────────────────────────────────────────────┐
     │                  Clinical HRV Record                  │
     │           (59 features, 4,314-record dataset)         │
     └──────────────────────┬───────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  FastAPI Layer  │  ← REST API, Auth, Routing
                    └───────┬────────┘
                            │
               ┌────────────▼────────────┐
               │   LangGraph Agent Graph  │
               │                         │
               │  1. validation          │
               │  2. feature_analysis    │  ← Claude Haiku 4.5
               │  3. anomaly_detection   │
               │  4. ml_scoring          │  ← XGBoost + SMOTE
               │  5. rag_retrieval       │  ← LanceDB + Titan Embeddings
               │  6. clinical_interp.    │  ← Claude Sonnet 4
               │  7. recommendation      │  ← Claude Haiku 4.5
               │  8. synthesis           │  ← Claude Sonnet 4
               └────────────┬────────────┘
                            │
               ┌────────────▼────────────┐
               │    AWS Bedrock (Claude)  │  us-west-2 cross-region
               │    LanceDB (RAG store)   │
               └─────────────────────────┘
```

---

## Project Structure

```
HRV/
├── hrv-agent/                  # Backend (Python)
│   ├── agents/
│   │   ├── graph.py            # LangGraph pipeline definition
│   │   ├── state.py            # Shared agent state schema
│   │   └── nodes/              # 8 agent node implementations
│   │       ├── validation.py
│   │       ├── feature_analysis.py
│   │       ├── anomaly_detection.py
│   │       ├── ml_scoring.py
│   │       ├── rag_retrieval.py
│   │       ├── clinical_interpretation.py
│   │       ├── recommendation.py
│   │       └── synthesis.py
│   ├── api/
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── auth.py             # API key authentication
│   │   └── routes/
│   │       ├── analyze.py      # /analyze/single, /analyze/batch
│   │       ├── chat.py         # /chat (HRV coach)
│   │       └── metrics.py      # /health, /model/metrics
│   ├── bedrock/
│   │   ├── client.py           # ChatBedrockConverse clients (lazy-loaded)
│   │   └── prompts.py          # System prompts for each node
│   ├── data/
│   │   ├── models.py           # Pydantic v2 schemas (59 HRV features)
│   │   ├── loader.py           # Excel dataset loader + validator
│   │   └── vector_store.py     # LanceDB + Amazon Titan Embeddings
│   ├── ml/
│   │   ├── features.py         # Feature engineering (composite risk score)
│   │   ├── classifier.py       # XGBoost + isotonic calibration
│   │   ├── trainer.py          # Training pipeline (SMOTE + threshold opt.)
│   │   └── models/
│   │       └── xgb_hrv_v1.pkl  # Trained model artifact
│   ├── observability/
│   │   ├── telemetry.py        # Node & pipeline telemetry
│   │   └── evaluation.py       # ML metrics persistence
│   ├── tests/
│   │   ├── test_loader.py
│   │   ├── test_agents.py
│   │   └── test_classifier.py
│   ├── .env                    # Environment variables (not committed)
│   ├── requirements.txt
│   └── Dockerfile
│
└── hrv-dashboard/              # Frontend (React + Vite)
    ├── src/
    │   ├── App.jsx             # Two-panel layout (75% dashboard / 25% coach)
    │   ├── data.js             # 30-day HRV data generator + helpers
    │   ├── index.css           # Dark theme design system
    │   └── components/
    │       ├── Cards.jsx       # MetricCard, TodaySnapshot, Badge
    │       ├── Charts.jsx      # HRVChart, RecoveryChart, SleepStrainChart
    │       └── AICoach.jsx     # Chat panel → /chat API
    └── vite.config.js
```

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- AWS account with Bedrock access (us-west-2)

### 1. Clone and set up Python environment

```bash
git clone <repo-url>
cd HRV
python3 -m venv .venv
source .venv/bin/activate
pip install -r hrv-agent/requirements.txt
```

### 2. Configure environment

```bash
cp hrv-agent/.env.example hrv-agent/.env
```

Edit `hrv-agent/.env`:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-west-2

# Active Claude 4 models (cross-region inference profiles)
BEDROCK_SONNET_MODEL=us.anthropic.claude-sonnet-4-20250514-v1:0
BEDROCK_HAIKU_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0

HRV_API_KEY=hrv-agent-dev-key-2024
MODEL_PATH=ml/models/xgb_hrv_v1.pkl
DATA_PATH=../HRV data 20201209 2.xlsx
```

### 3. Train the ML model (one-time)

```bash
cd hrv-agent
PYTHONPATH=. python ml/trainer.py "../HRV data 20201209 2.xlsx" ml/models/xgb_hrv_v1.pkl
# Expected: AUC-ROC ≈ 0.93, Recall ≈ 0.73 at threshold 0.10
```

### 4. Start the backend API

```bash
PYTHONPATH=. /path/to/.venv/bin/python api/main.py
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 5. Start the frontend dashboard

```bash
cd ../hrv-dashboard
npm install
npm run dev
# → http://localhost:5173
```

---

## ML Model

### Dataset
- **Source:** Clinical HRV Research Dataset (`HRV_data_20201209_2.xlsx`)
- **Records:** 4,314 patient observations
- **Target:** `Sepsis3` (binary: 0 = no sepsis, 1 = sepsis)
- **Class balance:** 3,776 negative / 538 positive (~7:1 imbalance)
- **Features:** 59 HRV biomarkers across 5 domains

### Feature Domains

| Domain | Examples | Clinical Relevance |
|---|---|---|
| Time-domain | RMSSD, SDNN, Mean HR | Overall HRV magnitude |
| Poincaré | SD1, SD2, SD1/SD2 ratio | Short vs long-term variability |
| Frequency | LF/HF ratio, LF Power, HF Power | Sympathovagal balance |
| Nonlinear | DFA α1/α2, Lyapunov, Hurst | Fractal dynamics |
| Entropy | Multiscale Entropy, Shannon, KLPE | Biological complexity |

### Training Pipeline

```
Raw data (4,314 records)
    → Feature engineering (composite risk score, 4 interaction features)
    → Stratified 80/20 split
    → SMOTE oversampling (training set only)
    → XGBoost (scale_pos_weight=7.0)
    → Isotonic probability calibration
    → Threshold optimization (max F1 @ recall ≥ 0.75)
```

### Performance

| Metric | Value | Target |
|---|---|---|
| AUC-ROC | **0.9311** | > 0.80 ✅ |
| Recall (sepsis) | 0.73 | ≥ 0.75 |
| Threshold | 0.10 | — |
| Risk tiers | LOW / MODERATE / HIGH / CRITICAL | — |

### Risk Stratification

| Risk Level | Probability | Action |
|---|---|---|
| LOW | < 0.15 | Routine monitoring |
| MODERATE | 0.15 – 0.40 | Reassess in 4h, labs |
| HIGH | 0.40 – 0.65 | Intensivist review, sepsis workup |
| CRITICAL | > 0.65 | Immediate escalation, vasopressor prep |

---

## Agent Pipeline

The system uses a **LangGraph `StateGraph`** with 8 sequential nodes and one conditional branch:

```
validation
    → feature_analysis      (Claude Haiku 4.5 — fast domain identification)
    → anomaly_detection      (deterministic Z-score + IQR, clinical thresholds)
    → ml_scoring             (XGBoost probability + composite risk blend)
    → rag_retrieval          (LanceDB similarity search — skip in "quick" mode)
    → clinical_interpretation (Claude Sonnet 4 — deep autonomic analysis)
    → recommendation         (Claude Haiku 4.5 — priority-ordered actions)
    → synthesis              (Claude Sonnet 4 — structured clinical briefing)
```

Every LLM node has a **deterministic fallback**: if Bedrock is unavailable, the node returns templated output based on risk level and anomaly count. The pipeline never fails hard.

### Agent State

```python
class HRVAgentState(TypedDict):
    records: list[HRVRecord]
    analysis_mode: str          # "full" | "quick"
    feature_groups: dict
    anomalies: list[Anomaly]
    risk_scores: list[float]
    risk_levels: list[RiskLevel]
    clinical_interpretation: str
    recommendations: list[str]
    processing_metadata: dict
```

---

## API Reference

Base URL: `http://localhost:8000`  
Authentication: `X-API-Key: hrv-agent-dev-key-2024` (header)

### Endpoints

#### `GET /health`
Returns system status (no auth required).

```json
{
  "status": "healthy",
  "model_loaded": true,
  "bedrock_region": "us-west-2"
}
```

#### `POST /analyze/single`
Run the full 8-node agent pipeline on one HRV record.

**Request body:** Any valid HRV record with 59 feature fields (see `/docs` for full schema).

**Response:**
```json
{
  "risk_level": "moderate",
  "sepsis_probability": 0.356,
  "anomalies": [
    {"feature": "LF.HF.ratio.LombScargle", "severity": "critical", "value": 6.8, "threshold": 3.0},
    {"feature": "DFA.Alpha.1", "severity": "critical", "value": 0.32, "threshold": 0.5}
  ],
  "clinical_interpretation": "Severe autonomic dysfunction consistent with septic physiology...",
  "recommendations": ["IMMEDIATE ESCALATION — activate sepsis protocol within 30 minutes.", "..."],
  "processing_metadata": {
    "total_latency_ms": 3440,
    "estimated_bedrock_cost_usd": 0.014
  }
}
```

#### `POST /analyze/batch`
Same as above, accepts a list of records.

#### `POST /chat`
Conversational HRV coach. Claude Sonnet 4 responds with structured clinical guidance.

```json
// Request
{ "message": "What does a high LF/HF ratio mean for sepsis risk?" }

// Response
{ "reply": "SUMMARY: Elevated LF/HF ratio indicates sympathetic dominance...", "sources": [] }
```

#### `GET /model/metrics`
Returns the latest XGBoost evaluation results (AUC-ROC, precision, recall, F1).

---

## Frontend Dashboard

The React dashboard (`hrv-dashboard/`) provides a two-panel interface:

- **Left panel (75%):** Today's snapshot (recovery ring, HRV/Sleep/Strain/SDNN), 30-day metric cards, interactive trend charts (HRV area, Recovery bar, Sleep & Strain line)
- **Right panel (25%):** AI Recovery Coach — full-height chat powered by the `/chat` endpoint

**Tech:** Vite + React + Recharts — zero external CSS frameworks.

---

## AWS Bedrock Configuration

This project requires AWS Bedrock access in `us-west-2` with the following **ACTIVE** models enabled in your account:

| Role | Model ID | Used For |
|---|---|---|
| Deep reasoning | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Clinical interpretation, synthesis |
| Fast inference | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Feature analysis, recommendations, chat |
| Embeddings | `amazon.titan-embed-text-v2:0` | LanceDB RAG vector store |

> **Note:** The `us.` prefix is required — these are cross-region inference profiles. Bare model IDs (without `us.`) will return a `ValidationException`.

To enable models: AWS Console → Bedrock → Model Access → Request access.

---

## Running Tests

```bash
cd hrv-agent
PYTHONPATH=. pytest tests/ -v

# Expected output:
# tests/test_loader.py::test_load_excel PASSED
# tests/test_agents.py::test_validation_node PASSED
# tests/test_classifier.py::test_risk_levels PASSED
# ... 18 passed in ~4s
```

---

## Deployment

### Docker (local)

```bash
cd hrv-agent
docker build -t hrv-agent:latest .
docker run -p 8000:8000 --env-file .env hrv-agent:latest
```

### Docker Compose (with persistent volumes)

```bash
docker-compose up -d
# Mounts ml/models/ and lancedb/ as persistent volumes
```

### AWS Lambda (Serverless)

The API includes a [Mangum](https://mangum.io/) adapter for Lambda deployment:

```python
# api/main.py
from mangum import Mangum
handler = Mangum(app, lifespan="off")
```

Deploy via the provided GitHub Actions workflow (`.github/workflows/deploy.yml`).

---

## Performance Results

| Component | Metric | Value |
|---|---|---|
| ML Model | AUC-ROC | **0.9311** |
| ML Model | Sepsis recall | 0.73 |
| End-to-end pipeline | Latency (full mode) | ~3–27s* |
| Claude Sonnet 4 | Cost per analysis | ~$0.014 |
| Unit tests | Pass rate | 18/18 |

*Latency varies by Bedrock response time. Deterministic fallback completes in ~3s regardless.

---

## License

MIT License — see `LICENSE` file.

---

*Built for the WHOOP AI Engineer portfolio — demonstrating clinical HRV science, agentic AI engineering, and production MLOps.*
