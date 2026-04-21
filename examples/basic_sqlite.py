"""Basic SQLite cache example.

SQLite fills the gap between InMemory (non-persistent, single-process) and
Redis (distributed, needs a server). Ideal for CLIs, desktop apps, and
single-VM services.
"""

from cachine import SQLiteCache


def main() -> None:
    # Simple path form — no config object needed
    cache = SQLiteCache(database="/tmp/example_cache.db", namespace="demo")
    cache.set("hello", "world", ttl=60)
    print(cache.get("hello"))

    # In-memory variant (ephemeral, per-process)
    ephemeral = SQLiteCache(database=":memory:", namespace="ephemeral")
    ephemeral.set("count", 1)
    print("count:", ephemeral.get("count"))
    ephemeral.close()

    # URL form (env var friendly)
    from_url = SQLiteCache.from_url("sqlite:///:memory:", namespace="url")
    from_url.set("via_url", True)
    print("via_url:", from_url.get("via_url"))
    from_url.close()

    cache.close()


if __name__ == "__main__":
    main()
