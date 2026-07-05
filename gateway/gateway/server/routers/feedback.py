"""Feedback API router."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from gateway.core.learning.feedback import get_feedback_store
from gateway.core.learning.scorer_weights import get_scorer_weights
from gateway.server.schemas.requests import FeedbackRequest
from gateway.server.schemas.responses import FeedbackResponse
from gateway.storage.database import async_session_factory
from gateway.storage.models import Feedback

router = APIRouter()


@router.post("", response_model=FeedbackResponse)
@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """Submit feedback for a context session."""
    feedback_payload = request.model_dump()
    try:
        session_uuid = UUID(request.session_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid session_id") from e

    try:
        async with async_session_factory() as db:
            result = await db.execute(
                select(Feedback).where(Feedback.session_id == session_uuid)
            )
            feedback = result.scalar_one_or_none()
            if feedback is None:
                feedback = Feedback(session_id=session_uuid)
                db.add(feedback)

            feedback.rating = request.rating
            feedback.was_helpful = request.was_helpful
            feedback.missing_context = request.missing_context
            feedback.irrelevant_context = request.irrelevant_context
            feedback.comment = request.comment
            feedback.prompt_id = UUID(request.prompt_id) if request.prompt_id else None
            await db.commit()

        await get_feedback_store().add_feedback(request.session_id, feedback_payload)
        await get_scorer_weights().adjust_weights_from_feedback(feedback_payload)

        return FeedbackResponse(status="ok", session_id=request.session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
