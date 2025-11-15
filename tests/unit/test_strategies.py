from cachine import InMemoryCache
from cachine.strategies import TagBasedInvalidation


def test_tag_invalid_stub():
    inv = TagBasedInvalidation(InMemoryCache())
    # Just ensure methods exist; no real behavior in scaffold
    # async wrappers are not exercised here.
    assert inv is not None
