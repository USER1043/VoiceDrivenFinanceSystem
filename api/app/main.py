from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import auth, health, me

API_PREFIX = "/api"
MEDIA_TYPES = {".webmanifest": "application/manifest+json"}
NO_CACHE = {"Cache-Control": "no-cache"}
NO_CACHE_FILES = {"sw.js", "registerSW.js", "manifest.webmanifest"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VoxFin",
        version="2.0.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    app.middleware("http")(_reject_cross_origin_writes)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(me.router, prefix=API_PREFIX)

    # Serve the built PWA from the same origin (one hostname, cookie auth, no CORS).
    dist = Path(settings.web_dist_dir)
    if (dist / "index.html").is_file():
        _mount_spa(app, dist)
    return app


async def _reject_cross_origin_writes(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """CSRF defence on top of SameSite=Lax cookies: browsers send Origin on writes, and it
    must match the host serving the app."""
    origin = request.headers.get("origin")
    if (
        request.method not in SAFE_METHODS
        and origin
        and urlsplit(origin).netloc != request.headers.get("host")
    ):
        return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)
    return await call_next(request)


def _mount_spa(app: FastAPI, dist: Path) -> None:
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    index = dist / "index.html"
    root = dist.resolve()

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            # Manifest, service worker, icons. The service worker and index must never be
            # cached by the browser, or app updates would not reach the phone.
            return FileResponse(
                candidate,
                media_type=MEDIA_TYPES.get(candidate.suffix),
                headers=NO_CACHE if candidate.name in NO_CACHE_FILES else None,
            )
        return FileResponse(index, headers=NO_CACHE)


app = create_app()
