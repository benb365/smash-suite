from __future__ import annotations
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class RallyInterval:
    rally_id: int
    start_ms: float
    end_ms: float
    emitted_at_ms: float

    def __post_init__(self) -> None:
        if type(self.rally_id) is not int:
            raise ValueError("Rally id must be an integer.")
        if not all(math.isfinite(value) for value in (self.start_ms, self.end_ms, self.emitted_at_ms)):
            raise ValueError("Rally times must be finite.")
        if not self.start_ms <= self.end_ms <= self.emitted_at_ms:
            raise ValueError("Rally requires start_ms <= end_ms <= emitted_at_ms.")
