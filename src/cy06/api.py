"""Local HTTP API for CY-06 analysis."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .chat import ChatError, run_chat
from .config import load_project_env
from .connector import EXPECTED_ROLE_ARN, collect_inventory, connect
from .inventory import InventoryError
from .rules import analyze_inventory

@asynccontextmanager
async def lifespan(_app: FastAPI):
    load_project_env()
    yield


app = FastAPI(title="CY-06 API", version="0.1.0", lifespan=lifespan)


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
    return _load_fixture("simple-demo-iam-inventory.json")


@app.get("/api/v1/full-demo")
def full_demo() -> dict[str, Any]:
    return _load_fixture("sample-iam-inventory.json")


@app.get("/api/v1/live")
def live() -> dict[str, Any]:
    try:
        connection = connect(
            os.getenv("CY06_AWS_PROFILE", "cy06-dev"),
            EXPECTED_ROLE_ARN,
            "ap-south-1",
        )
        return collect_inventory(connection)
    except ConnectionError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


def _load_fixture(name: str) -> dict[str, Any]:
    fixture = Path(__file__).resolve().parents[2] / "data" / name
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
