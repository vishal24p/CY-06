"""Local HTTP API for CY-06 analysis."""

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .chat import ChatError, run_chat
from .inventory import InventoryError
from .rules import analyze_inventory

app = FastAPI(title="CY-06 API", version="0.1.0")


class AnalyzeRequest(BaseModel):
    """JSON request accepted by the local analyzer."""

    inventory: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """One user or assistant message accepted by chat."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4_000)


class ChatRequest(BaseModel):
    """Validated chat conversation sent to the local agent."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=20)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/demo")
def demo() -> dict[str, Any]:
    fixture = Path(__file__).resolve().parents[2] / "data" / "sample-iam-inventory.json"
    with fixture.open(encoding="utf-8") as stream:
        return json.load(stream)


@app.post("/api/v1/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    try:
        return analyze_inventory(request.inventory, request.context)
    except InventoryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/v1/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    try:
        return run_chat([message.model_dump() for message in request.messages])
    except ChatError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
