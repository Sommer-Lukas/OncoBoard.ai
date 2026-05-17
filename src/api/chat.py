"""Chat API — conversational RAG endpoint for the ClinicalContextAgent."""
from typing import Annotated, Literal

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.agents.ClinicalContextAgent import ClinicalContextAgent, Phase
from src.db.connection import get_db
from src.db import repository

router = APIRouter(prefix="/cases", tags=["chat"])

_Db = Annotated[aiosqlite.Connection, Depends(get_db)]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    phase: Phase = "pre"


class ChatResponse(BaseModel):
    reply: str


@router.post("/{case_id}/chat", response_model=ChatResponse)
async def chat(case_id: str, request: ChatRequest, db: _Db) -> ChatResponse:
    if not await repository.get_case(db, case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    if not request.messages or request.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="Last message must be from user")

    agent = ClinicalContextAgent()
    reply = await agent.chat(
        db,
        case_id,
        [m.model_dump() for m in request.messages],
        request.phase,
    )
    return ChatResponse(reply=reply)
