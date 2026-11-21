import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api import auth, clips, oauth, projects, uploads
from app.core.config import get_settings
from app.core.deps import get_storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("clipforge")


async def ensure_bucket(attempts: int = 15, delay: float = 2.0) -> None:
    """Create the storage bucket if it's missing. Storage may still be booting, so retry for a bit;
    never block startup forever (uploads will show a clear error if storage stays down)."""
    storage = get_storage()
    for attempt in range(1, attempts + 1):
        try:
            await asyncio.to_thread(storage.ensure_bucket)
            log.info("Storage bucket %r is ready", storage.bucket)
            return
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts:
                log.error("Storage bucket %r is not reachable: %s", storage.bucket, exc)
                return
            await asyncio.sleep(delay)


class CatchUnhandledErrors:
    """Turn an unexpected exception into a JSON 500 *inside* the CORS middleware.

    Without this, Starlette answers crashes from its outermost layer, which skips the CORS headers;
    the browser then hides the response and the web app wrongly reports that the API is unreachable.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def track(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track)
        except Exception:
            log.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:  # part of the response is already sent; nothing sensible left to do
                raise
            response = JSONResponse({"detail": "Something went wrong on the server. Please try again."}, status_code=500)
            await response(scope, receive, send)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await ensure_bucket()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ClipForge API", version="0.1.0", docs_url="/docs", openapi_url="/openapi.json", lifespan=lifespan
    )

    # Added first so it sits inside CORS (the last middleware added is the outermost).
    app.add_middleware(CatchUnhandledErrors)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,  # needed for the auth cookie
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for module in (auth, uploads, projects, clips, oauth):
        app.include_router(module.router, prefix="/api")

    @app.get("/api/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
