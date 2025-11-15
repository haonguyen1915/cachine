from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Serializer(ABC):
    @abstractmethod
    def dumps(self, value: Any) -> bytes:  # pragma: no cover - abstract
        ...

    @abstractmethod
    def loads(self, data: bytes) -> Any:  # pragma: no cover - abstract
        ...
