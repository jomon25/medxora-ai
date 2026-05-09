from __future__ import annotations
import json
from collections import defaultdict
from fastapi import WebSocket

class WebSocketManager:
    def __init__(self):
        self.mission_clients = defaultdict(set)
        self.evolution_clients = set()

    async def connect_mission(self, mission_id: str, ws: WebSocket):
        await ws.accept()
        self.mission_clients[mission_id].add(ws)

    async def connect_evolution(self, ws: WebSocket):
        await ws.accept()
        self.evolution_clients.add(ws)

    def disconnect_mission(self, mission_id: str, ws: WebSocket):
        self.mission_clients[mission_id].discard(ws)

    def disconnect_evolution(self, ws: WebSocket):
        self.evolution_clients.discard(ws)

    async def broadcast_mission(self, mission_id: str, payload: dict):
        for ws in list(self.mission_clients.get(mission_id, set())):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.disconnect_mission(mission_id, ws)

    async def broadcast_evolution(self, payload: dict):
        for ws in list(self.evolution_clients):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.disconnect_evolution(ws)

ws_manager = WebSocketManager()
