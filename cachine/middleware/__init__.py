"""Cachine middleware.

All built-in middleware is re-exported here so users never have to import
from submodules::

    from cachine.middleware import (
        CompressionMiddleware,
        EncryptionMiddleware,
        FailOpenMiddleware,
        AsyncFailOpenMiddleware,
        MetricsMiddleware,
        AsyncMetricsMiddleware,
    )
"""

from .base import AsyncCacheMiddleware, BaseMiddleware, SyncCacheMiddleware
from .compression import CompressionMiddleware
from .encryption import EncryptionMiddleware
from .fail_open import AsyncFailOpenMiddleware, FailOpenMiddleware
from .metrics import AsyncMetricsMiddleware, MetricsMiddleware

__all__ = [
    # Base classes
    "BaseMiddleware",
    "SyncCacheMiddleware",
    "AsyncCacheMiddleware",
    # Sync middleware
    "CompressionMiddleware",
    "EncryptionMiddleware",
    "FailOpenMiddleware",
    "MetricsMiddleware",
    # Async middleware
    "AsyncFailOpenMiddleware",
    "AsyncMetricsMiddleware",
]
