"""
AI Schemas module (app/schemas/ai.py).
Re-exports and centralizes all AI schemas according to Unified Experience standard.
"""
from app.schemas.common import StandardResponse
from app.schemas_ai import (
    RefundContextForAI,
    AIRecommendationResponse,
    AIChatRequest,
    CreateRefundArgs,
    ApproveRefundArgs,
    RejectRefundArgs,
    ExecutePendingActionRequest,
)

__all__ = [
    "StandardResponse",
    "RefundContextForAI",
    "AIRecommendationResponse",
    "AIChatRequest",
    "CreateRefundArgs",
    "ApproveRefundArgs",
    "RejectRefundArgs",
    "ExecutePendingActionRequest",
]
