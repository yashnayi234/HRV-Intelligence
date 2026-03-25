"""Chat route — multi-turn conversational HRV coach."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agents.graph import run_hrv_pipeline
from api.auth import verify_api_key
from bedrock.prompts import COACH_SYSTEM
from data.models import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["Coach"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _: str = Depends(verify_api_key),
) -> ChatResponse:
    """
    Multi-turn HRV conversational coach.

    If context_records provided, the full pipeline runs first and the
    coach response is augmented with the analysis results.
    """
    sources: list[dict] = []
    pipeline_context = ""

    if request.context_records:
        state = await run_hrv_pipeline(
            request.context_records,
            analysis_mode="full",
            user_query=request.message,
        )
        pipeline_context = state.get("coach_response", "")
        sources = [
            {"type": "hrv_analysis", "content": pipeline_context[:500]}
        ]

    # Conversational LLM call via Haiku (fast)
    reply = pipeline_context if pipeline_context else ""

    try:
        from bedrock.client import llm_haiku
        from langchain_core.messages import HumanMessage, SystemMessage

        system = COACH_SYSTEM
        user_msg = request.message
        if pipeline_context:
            user_msg = f"Context from HRV analysis:\n{pipeline_context}\n\nUser question: {request.message}"

        response = await llm_haiku.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user_msg),
        ])
        reply = str(response.content)

    except Exception as e:
        import traceback
        import sys
        print(f"ERROR calling Bedrock: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        if not reply:
            reply = (
                "I'm the HRV clinical coach. Please provide HRV records for analysis, "
                "or ask me about HRV biomarkers, sepsis risk, or autonomic physiology."
            )

    return ChatResponse(reply=reply, sources=sources)
