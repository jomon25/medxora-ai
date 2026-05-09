from __future__ import annotations
import time
import json
import logging
from datetime import datetime
from services.agentic_foundation import add_event

class BaseAgent:
    def __init__(self, metadata: dict):
        self.meta = metadata
        self.status = "idle"
        self.current_task = ""
        self.last_output = None
        self.confidence = 0.0
        self.cost_used = 0.0
        self.time_used_ms = 0
        self.last_updated = None

    def snapshot(self):
        return {**self.meta, "status": self.status, "current_task": self.current_task, "last_output": self.last_output,
                "confidence": self.confidence, "cost_used": self.cost_used, "time_used_ms": self.time_used_ms,
                "last_updated": self.last_updated}

    def emit(self, mission_id, stage, status, event_type, message, details=None):
        logging.getLogger("medxora.agent").info(json.dumps({
            "event": f"agent_{status}",
            "mission_id": mission_id,
            "agent": self.meta["name"],
            "stage": stage,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
        }))
        add_event(mission_id, self.meta["name"], status, stage, message, event_type, details or {},
                  agent_id=self.meta["id"], agent_name=self.meta["name"], confidence=self.confidence,
                  time_used_ms=self.time_used_ms, cost_used=self.cost_used)

    def execute(self, mission_id: str, payload: dict, context: dict):
        started = time.time(); self.status = "running"; self.current_task = self.meta.get("goal", "working")
        self.emit(mission_id, self.meta.get("id"), "running", "info", f"{self.meta['name']} started")
        out = self.run(payload, context)
        self.time_used_ms = int((time.time() - started) * 1000)
        self.status = "completed"; self.last_output = out; self.last_updated = datetime.utcnow().isoformat(); self.confidence = out.get("confidence", 0.8)
        self.emit(mission_id, self.meta.get("id"), "completed", "success", f"{self.meta['name']} completed", out)
        return out

    def run(self, payload: dict, context: dict):
        raise NotImplementedError
