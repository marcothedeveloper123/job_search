"""WebSocket support for real-time UI updates."""

import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

# Connected clients
_clients: set[WebSocket] = set()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint handler."""
    await websocket.accept()
    _clients.add(websocket)
    try:
        while True:
            # Keep connection alive, ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        _clients.discard(websocket)


def broadcast(event: str, data: dict[str, Any] | None = None):
    """
    Broadcast event to all connected clients.

    Can be called from sync code - handles async internally.
    """
    message = json.dumps({"event": event, "data": data or {}})

    async def _send():
        disconnected = []
        for client in _clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.append(client)
        for client in disconnected:
            _clients.discard(client)

    # Try to get running loop, create one if needed
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send())
    except RuntimeError:
        # No running loop - run synchronously
        asyncio.run(_send())


def broadcast_jobs_updated():
    """Notify clients that job results have been updated."""
    broadcast("jobs_updated")


def broadcast_deep_dive_updated(job_id: str):
    """Notify clients that a deep dive has been updated."""
    broadcast("deep_dive_updated", {"job_id": job_id})


def broadcast_application_updated(application_id: str):
    """Notify clients that an application has been updated."""
    broadcast("application_updated", {"application_id": application_id})


def broadcast_applications_changed():
    """Notify clients that applications list has changed (add/delete/archive)."""
    broadcast("applications_changed")


def broadcast_deep_dives_changed():
    """Notify clients that deep dives list has changed (add/delete/archive)."""
    broadcast("deep_dives_changed")


def broadcast_selection_changed():
    """Notify clients that selections have changed."""
    broadcast("selection_changed")


def broadcast_view_changed(view: str):
    """Notify clients to change the current view."""
    broadcast("view_changed", {"view": view})
