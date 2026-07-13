"""WebSocket connection manager (not implemented)."""

from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manage active WebSocket connections for live log and status streaming."""

    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        raise NotImplementedError("ConnectionManager.connect is not implemented")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active pool."""
        raise NotImplementedError("ConnectionManager.disconnect is not implemented")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a message to all connected clients."""
        raise NotImplementedError("ConnectionManager.broadcast is not implemented")

    async def send_personal(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Send a message to a single client."""
        raise NotImplementedError("ConnectionManager.send_personal is not implemented")
