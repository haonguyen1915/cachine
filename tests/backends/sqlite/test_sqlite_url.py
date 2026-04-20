import pytest

from cachine import async_cache_from_url, cache_from_url
from cachine.backends.sqlite.async_ import AsyncSQLiteCache
from cachine.backends.sqlite.sync import SQLiteCache
from cachine.utils.sqlite_url import SQLiteURLParseError, parse_sqlite_url


def test_parse_memory() -> None:
    cfg = parse_sqlite_url("sqlite:///:memory:")
    assert cfg.database == ":memory:"
    assert cfg.timeout == 5.0
    assert cfg.journal_mode == "WAL"


def test_parse_file_path() -> None:
    cfg = parse_sqlite_url("sqlite:///tmp/cache.db")
    assert cfg.database == "tmp/cache.db"


def test_parse_absolute_file_path() -> None:
    cfg = parse_sqlite_url("sqlite:////abs/path/cache.db")
    assert cfg.database == "/abs/path/cache.db"


def test_parse_with_params() -> None:
    cfg = parse_sqlite_url("sqlite:///tmp/db?timeout=10&busy_timeout=2000&journal_mode=DELETE&synchronous=FULL&check_same_thread=true")
    assert cfg.timeout == 10.0
    assert cfg.busy_timeout_ms == 2000
    assert cfg.journal_mode == "DELETE"
    assert cfg.synchronous == "FULL"
    assert cfg.check_same_thread is True


def test_empty_url_raises() -> None:
    with pytest.raises(SQLiteURLParseError):
        parse_sqlite_url("")


def test_unsupported_scheme_raises() -> None:
    with pytest.raises(SQLiteURLParseError):
        parse_sqlite_url("redis://localhost")


def test_cache_from_url_sync() -> None:
    cache = cache_from_url("sqlite:///:memory:", namespace="t")
    assert isinstance(cache, SQLiteCache)
    try:
        cache.set("a", b"1")
        assert cache.get("a") == b"1"
    finally:
        cache.close()


def test_async_cache_from_url() -> None:
    cache = async_cache_from_url("sqlite:///:memory:", namespace="t")
    assert isinstance(cache, AsyncSQLiteCache)
