from __future__ import annotations

from typing import Any

from ..exceptions import DeserializationError, SerializationError
from .base import Serializer


class MsgPackSerializer(Serializer):
    """Serialize values using MessagePack (msgpack).

    Requires the ``msgpack`` package.
    """

    def dumps(self, value: Any) -> bytes:
        """Serialize to MessagePack bytes.

        Args:
            value (Any): Python object to serialize.

        Returns:
            bytes: Encoded payload.

        Raises:
            SerializationError: If msgpack is missing or serialization fails.
        """
        try:
            import msgpack

            result: bytes = msgpack.dumps(value, use_bin_type=True)
            return result
        except ModuleNotFoundError as e:  # pragma: no cover
            raise SerializationError("msgpack is not installed") from e
        except Exception as e:  # pragma: no cover
            raise SerializationError(str(e)) from e

    def loads(self, data: bytes) -> Any:
        """Deserialize MessagePack bytes.

        Args:
            data (bytes): Encoded payload.

        Returns:
            Any: Decoded Python object.

        Raises:
            DeserializationError: If msgpack is missing or deserialization fails.
        """
        try:
            import msgpack

            return msgpack.loads(data, raw=False)
        except ModuleNotFoundError as e:  # pragma: no cover
            raise DeserializationError("msgpack is not installed") from e
        except Exception as e:  # pragma: no cover
            raise DeserializationError(str(e)) from e
