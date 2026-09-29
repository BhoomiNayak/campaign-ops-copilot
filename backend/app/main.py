"""FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload --port 8000

Interactive OpenAPI docs are served at /docs (Swagger) and /redoc.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import APP_DESCRIPTION, APP_TITLE, APP_VERSION

app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
)

# Location of the built frontend. Override with FRONTEND_DIST if needed.
# .../backend/app/main.py -> parents[2] is the project root.
FRONTEND_DIST = Path(
    os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist")
)

# During local development the Vite dev server proxies /api to this backend,
# so CORS is not strictly required. It is enabled for localhost origins to keep
# direct-from-browser calls working if the proxy is bypassed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# In production (single-service hosting), serve the built React app from the
# same origin so the frontend's relative "/api" calls just work — no CORS, no
# separate host, no configuration. The API router above is registered first, so
# /api/* and /docs always take precedence over these static files.
#
# If the build isn't present (typical during local dev, where Vite serves the
# frontend and proxies /api), we fall back to a small JSON landing payload.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
else:

    @app.get("/", tags=["system"], include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": APP_TITLE,
            "version": APP_VERSION,
            "docs": "/docs",
            "health": "/api/health",
        }
