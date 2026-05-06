"""Endpoints /feedback y /admin/pending."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.dependencies import get_repository_dep
from backend.api.schemas import FeedbackRequest, FeedbackResponse
from backend.repository import InteractionRepository

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse)
def feedback(
    req: FeedbackRequest,
    repo: InteractionRepository = Depends(get_repository_dep),
) -> FeedbackResponse:
    ok = repo.save_feedback(req.interaction_id, req.helpful, req.comment)
    if not ok:
        raise HTTPException(
            status_code=404, detail=f"interaction_id no encontrado: {req.interaction_id}"
        )
    return FeedbackResponse(ok=True, interaction_id=req.interaction_id)


@router.get("/admin/pending")
def pending(
    limit: int = 50,
    repo: InteractionRepository = Depends(get_repository_dep),
) -> list[dict]:
    return repo.pending_feedback(limit=limit)
