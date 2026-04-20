from __future__ import annotations

import os
import time

import pytest

from cachine.serializers import JSONSerializer, PickleSerializer


def _truthy(v: str | None) -> bool:
    return (v or "").lower() in {"1", "true", "yes", "on"}


perf_enabled = pytest.mark.skipif(not _truthy(os.getenv("RUN_PERF_TESTS")), reason="RUN_PERF_TESTS not enabled")


@perf_enabled
def test_json_vs_pickle_roundtrip_perf() -> None:
    payload = {
        "a": list(range(100)),
        "b": {str(i): i for i in range(100)},
        "c": "x" * 1000,
    }
    N = int(os.getenv("PERF_N", "2000"))

    js = JSONSerializer()
    ps = PickleSerializer()

    # JSON
    t0 = time.perf_counter()
    for _ in range(N):
        b = js.dumps(payload)
        obj = js.loads(b)
        assert obj["c"].endswith("x")
    json_elapsed = time.perf_counter() - t0

    # Pickle
    t1 = time.perf_counter()
    for _ in range(N):
        b = ps.dumps(payload)
        obj = ps.loads(b)
        assert obj["c"].endswith("x")
    pickle_elapsed = time.perf_counter() - t1

    print(f"JSON roundtrip: {N / json_elapsed:,.0f} ops/s; Pickle roundtrip: {N / pickle_elapsed:,.0f} ops/s (N={N})")
