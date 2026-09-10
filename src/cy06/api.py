"""Local HTTP API for CY-06 analysis."""

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .inventory import InventoryError
from .rules import analyze_inventory

app = FastAPI(title="CY-06 API", version="0.1.0")


class AnalyzeRequest(BaseModel):
    """JSON request accepted by the local analyzer."""

    inventory: dict[str, Any]
    context: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    try:
        return analyze_inventory(request.inventory, request.context)
    except InventoryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
