"""Base connector interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConnectorResult:
    """Standardized result from any connector."""
    source: str
    data_type: str   # "event", "email", "message", "task", "reminder", "note"
    items: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_summary(self, max_items: int = 10) -> str:
        if self.error:
            return f"[{self.source}] Error: {self.error}"
        if not self.items:
            return f"[{self.source}] No {self.data_type}s found."
        lines = [f"[{self.source}] {len(self.items)} {self.data_type}(s):"]
        for item in self.items[:max_items]:
            lines.append(f"  - {item.get('title') or item.get('subject') or item.get('text', '')[:80]}")
        if len(self.items) > max_items:
            lines.append(f"  ... and {len(self.items) - max_items} more")
        return "\n".join(lines)


class BaseConnector(ABC):
    """Abstract base for all data connectors."""

    name: str = "base"
    enabled: bool = False

    @abstractmethod
    async def fetch(self) -> ConnectorResult:
        """Fetch latest data from this source."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this connector is properly configured."""
        ...

    async def safe_fetch(self) -> ConnectorResult:
        """Fetch with error handling."""
        if not self.is_available():
            return ConnectorResult(
                source=self.name,
                data_type="unknown",
                error="Connector not configured",
            )
        try:
            return await self.fetch()
        except Exception as e:
            return ConnectorResult(
                source=self.name,
                data_type="unknown",
                error=str(e),
            )
