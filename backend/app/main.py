"""Ponto de entrada do backend ARKHER AI.

Única porta de entrada do produto: navegador → este backend → modelo próprio.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app import config
from backend.app.api.routes import router
from backend.app.model import runtime as model_runtime
from backend.app.security.redact import get_logger
from backend.app.storage import db

log = get_logger("arkher")


def create_app() -> FastAPI:
    app = FastAPI(title="ARKHER AI API", version=config.VERSION, docs_url=None, redoc_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Arkher-Token"],
        max_age=600,
    )

    app.include_router(router)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.error("erro não tratado em %s: %s", request.url.path, type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"ok": False, "code": "INTERNAL", "message": "Erro interno do backend ARKHER."},
        )

    @app.on_event("startup")
    def startup() -> None:
        db.get_conn()
        model_runtime.ensure_loaded()
        log.info("ARKHER backend v%s pronto. Modelo: %s", config.VERSION, model_runtime.status()["state"])

    # Frontend estático (build do Vite), se existir
    if config.SERVE_FRONTEND and config.FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{rest:path}")
        async def spa(rest: str):
            if rest.startswith("api/"):
                return JSONResponse(status_code=404, content={"ok": False, "code": "NOT_FOUND", "message": "Rota inexistente."})
            alvo = config.FRONTEND_DIST / rest
            if rest and alvo.is_file():
                return FileResponse(alvo)
            return FileResponse(config.FRONTEND_DIST / "index.html")

    return app


app = create_app()
