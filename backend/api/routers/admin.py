"""Endpoints /admin/* — alimentan el dashboard logs-ui.

Solo lectura; pensados para bind ``127.0.0.1``. No exponer públicamente.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.dependencies import get_repository_dep, verify_admin_token
from backend.repository import InteractionRepository

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(verify_admin_token)],
)


@router.get("/summary")
def summary(
    repo: InteractionRepository = Depends(get_repository_dep),
) -> dict:
    return repo.summary()


@router.get("/logs")
def logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    organismo: str | None = None,
    intencion: str | None = None,
    conversation_id: str | None = None,
    repo: InteractionRepository = Depends(get_repository_dep),
) -> list[dict]:
    return repo.list_interactions(
        limit=limit,
        offset=offset,
        organismo=organismo,
        intencion=intencion,
        conversation_id=conversation_id,
    )


@router.get("/interactions/{interaction_id}")
def get_interaction(
    interaction_id: str,
    repo: InteractionRepository = Depends(get_repository_dep),
) -> dict:
    item = repo.get_interaction(interaction_id)
    if item is None:
        raise HTTPException(status_code=404, detail="interaction no encontrada")
    return item


@router.get("/conversations")
def conversations(
    limit: int = Query(50, ge=1, le=500),
    repo: InteractionRepository = Depends(get_repository_dep),
) -> list[dict]:
    return repo.list_conversations(limit=limit)


@router.get("/conversations/{conversation_id}")
def conversation_detail(
    conversation_id: str,
    repo: InteractionRepository = Depends(get_repository_dep),
) -> dict:
    turns = repo.get_conversation_turns(conversation_id)
    if not turns:
        raise HTTPException(status_code=404, detail="conversación no encontrada")
    return {"conversation_id": conversation_id, "turns": turns}
