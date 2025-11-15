from cachine import InMemoryCache


def main() -> None:
    cache = InMemoryCache()
    cache.set("hello", "world", ttl=60)
    print(cache.get("hello"))


if __name__ == "__main__":
    main()

