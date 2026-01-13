"""FastAPI server for job_search UI."""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from server.routes import router
from server.app_routes import router as app_router
from server.websocket import websocket_endpoint

app = FastAPI(title="job_search")

# CORS for dev (Vite runs on different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)
app.include_router(app_router)

# Paths
SERVER_DIR = Path(__file__).parent
DATA_DIR = SERVER_DIR / "data"
STATIC_DIR = SERVER_DIR / "static"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket_endpoint(websocket)


# Serve static files (React build) - mount last so API routes take precedence
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="127.0.0.1", port=8000, reload=True)
