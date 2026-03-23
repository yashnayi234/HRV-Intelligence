"""FastAPI application — HRV Agentic Intelligence System."""

from __future__ import annotations

import os
import sys

import structlog
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

from api.routes.analyze import router as analyze_router  # noqa: E402
from api.routes.chat import router as chat_router  # noqa: E402
from api.routes.metrics import router as metrics_router  # noqa: E402

# Add hrv-agent root to Python path for local imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(
    title="HRV Agentic Intelligence System",
    description=(
        "Production-grade multi-agent AI system for HRV-based sepsis risk detection. "
        "Powered by LangGraph + AWS Bedrock (Claude 3) + XGBoost + LanceDB RAG."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(analyze_router)
app.include_router(chat_router)
app.include_router(metrics_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Pre-warm classifier and log startup status."""
    logger = structlog.get_logger("startup")
    logger.info("HRV Agent API starting up")

    model_path = os.getenv("MODEL_PATH", "ml/models/xgb_hrv_v1.pkl")
    if os.path.exists(model_path):
        from agents.nodes.ml_scoring import _get_classifier
        clf = _get_classifier()
        logger.info("Classifier pre-warmed", model_loaded=clf._model is not None)
    else:
        logger.warning("Model not found — run ml/trainer.py first", path=model_path)

    logger.info(
        "API ready",
        docs="http://localhost:8000/docs",
        health="http://localhost:8000/health",
    )


# AWS Lambda adapter (Mangum)
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    pass


if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("ENV", "production") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
