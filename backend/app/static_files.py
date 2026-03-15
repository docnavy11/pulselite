from pathlib import Path

from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

STATIC_DIR = Path("/app/static")
ASSETS_DIR = STATIC_DIR / "assets"


def mount_frontend(app):
    """Mount built frontend static files with SPA fallback.

    Must be called AFTER all API routes are registered.
    """
    static_dir = STATIC_DIR
    assets_dir = ASSETS_DIR

    if not static_dir.exists():
        return

    # Serve Vite build assets with proper MIME types and caching
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static-assets")

    index_path = static_dir / "index.html"

    # SPA fallback: serve index.html for all unmatched GET routes
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(index_path)
