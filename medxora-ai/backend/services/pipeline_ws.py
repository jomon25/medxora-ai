from datetime import datetime
from typing import List

from fastapi import WebSocket


class PipelineWebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, stage: str, status: str, message: str, data=None):
        payload = {
            "time": datetime.now().isoformat(),
            "stage": stage,
            "status": status,
            "message": message,
            "data": data or {},
        }

        disconnected: list[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)


manager = PipelineWebSocketManager()
