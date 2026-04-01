"""Pharma Control Tower — FastAPI Application Entry Point.

Start with:
    uvicorn apps.api.app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.api.v1 import (
    inputs,
    orchestration,
    planner,
    demo_state,
    demo_operations,
    reports,
    mock_eta,
    dashboard,
)

app = FastAPI(
    title="Pharma Control Tower API",
    version="1.0.0",
    description="MVP planner-facing dispatch control tower backend.",
)

# ── CORS ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────
app.include_router(inputs.router)
app.include_router(orchestration.router)
app.include_router(planner.router)
app.include_router(demo_state.router)
app.include_router(demo_operations.router)
app.include_router(reports.router)
app.include_router(mock_eta.router)
app.include_router(dashboard.router)


@app.get("/", tags=["health"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "pharma-control-tower-api", "version": "1.0.0"}
