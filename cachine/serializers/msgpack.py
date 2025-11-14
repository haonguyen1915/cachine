from __future__ import annotations

from typing import Any

from ..exceptions import DeserializationError, SerializationError
from .base import Serializer


class MsgPackSerializer(Serializer):
    def dumps(self, value: Any) -> bytes:
        try:
            import msgpack  # type: ignore

            return msgpack.dumps(value, use_bin_type=True)
        except ModuleNotFoundError as e:  # pragma: no cover
            raise SerializationError("msgpack is not installed") from e
        except Exception as e:  # pragma: no cover
            raise SerializationError(str(e)) from e

    def loads(self, data: bytes) -> Any:
        try:
            import msgpack  # type: ignore

            return msgpack.loads(data, raw=False)
        except ModuleNotFoundError as e:  # pragma: no cover
            raise DeserializationError("msgpack is not installed") from e
        except Exception as e:  # pragma: no cover
            raise DeserializationError(str(e)) from e

