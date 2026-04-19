from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    id: str
    type: str                         # "heartbeat" | "cron"
    schedule: str                     # raw input string, kept for display
    task: str                         # natural language task description
    cron_expr: Optional[str] = None   # normalised 5-field cron expression (source of truth for runner)
    human_summary: str = ""           # plain English schedule description
    agent: Optional[str] = None
    output_mode: str = "verbose"      # "verbose" | "silent"
    enabled: bool = True
    created_at: str = ""
    last_run: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "schedule": self.schedule,
            "cron_expr": self.cron_expr,
            "human_summary": self.human_summary,
            "task": self.task,
            "agent": self.agent,
            "output_mode": self.output_mode,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_run": self.last_run,
        }

    @staticmethod
    def from_dict(d: dict) -> "Job":
        return Job(
            id=d["id"],
            type=d["type"],
            schedule=d["schedule"],
            cron_expr=d.get("cron_expr"),
            human_summary=d.get("human_summary", ""),
            task=d["task"],
            agent=d.get("agent"),
            output_mode=d.get("output_mode", "verbose"),
            enabled=d.get("enabled", True),
            created_at=d.get("created_at", ""),
            last_run=d.get("last_run"),
        )

    def schedule_summary(self) -> str:
        if self.human_summary:
            return self.human_summary
        if self.cron_expr:
            return self.cron_expr
        if self.type == "cron":
            return f"daily at {self.schedule}"
        return f"every {self.schedule}"
