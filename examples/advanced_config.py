from cachine import create_cache


def main() -> None:
    cache = create_cache({
        "backend": "redis",
        "host": "localhost",
        "port": 6379,
        "namespace": "myapp",
    }, mode="sync")
    with cache:
        cache.set("config", {"debug": True}, ttl=3600)
        print(cache.get("config"))


if __name__ == "__main__":
    main()

