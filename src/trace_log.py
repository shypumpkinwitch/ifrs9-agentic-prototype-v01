from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class TraceEntry:
    step: int
    tool: str
    reason: str
    arguments: dict[str, Any]
    observation: str
    elapsed_ms: float
    occurred_at_utc: str


@dataclass
class TraceLog:
    mode: str
    entries: list[TraceEntry] = field(default_factory=list)

    def add(
        self,
        *,
        tool: str,
        reason: str,
        arguments: dict[str, Any],
        observation: str,
        elapsed_ms: float,
    ) -> None:
        self.entries.append(
            TraceEntry(
                step=len(self.entries) + 1,
                tool=tool,
                reason=reason,
                arguments=arguments,
                observation=observation,
                elapsed_ms=round(elapsed_ms, 3),
                occurred_at_utc=datetime.now(timezone.utc).isoformat(),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "entries": [asdict(entry) for entry in self.entries]}
