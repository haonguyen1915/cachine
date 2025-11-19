import logging

from cachine.decorators._utils import build_cache_key  # adjust path accordingly

_logger = logging.getLogger(__name__)


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def build(fn, *args, key_builder=None, version=None, **kwargs):
    key = build_cache_key(
        fn=fn,
        key_builder=key_builder,
        version=version,
        args=args,
        kwargs=kwargs,
    )
    _logger.debug(f"Built key: {key}")
    return key


# -------------------------------------------------------------
# Test Case 1 — Plain function
# -------------------------------------------------------------

def test_build_key_plain_function():
    def add(x, y, __use_cache: bool = True):
        return x + y

    # With args
    k1 = build(add, 1, 2)
    k2 = build(add, 1, 2)
    # With kwargs
    k3 = build(add, x=1, y=2)
    # With version
    k4 = build(add, x=1, y=2, version="v1")
    k5 = build(add, x=1, y=2, version="v2")
    k6 = build(add, x=1, y=2, __use_cache=False)
    assert k1 == k2
    assert k1 != k3
    assert k3 != k4
    assert k1 != k5
    assert k4 != k6


# -------------------------------------------------------------
# Test Case 2 — Instance method
# -------------------------------------------------------------

class User:
    def __init__(self, uid):
        self.uid = uid

    def profile(self, detail=False):
        return {"id": self.uid}


def test_build_key_instance_method():
    u = User(123)
    k1 = build(u.profile, False)
    k2 = build(u.profile, True)
    k3 = build(u.profile, True)
    k4 = build(u.profile, detail=True)
    assert k1 != k2
    assert k2 == k3
    assert k3 != k4


# -------------------------------------------------------------
# Test Case 4 — classmethod
# -------------------------------------------------------------

class A:
    @classmethod
    def make(cls, x):
        return x


def test_build_key_classmethod():
    k1 = build(A.make, 99)
    k2 = build(A.make, 99)
    k3 = build(A.make, x=99)
    assert k1 == k2
    assert k1 != k3


# -------------------------------------------------------------
# Test Case 5 — staticmethod
# -------------------------------------------------------------

class S:
    @staticmethod
    def calc(a, b):
        return a + b


def test_build_key_staticmethod():
    k1 = build(S.calc, 5, 10)
    k2 = build(S.calc, 5, 10)
    k3 = build(S.calc, a=5, b=10)
    k4 = build(S.calc, b=10, a=5)
    k5 = build(S.calc, 5, b=10)
    assert k1 == k2
    assert k1 != k3
    assert k3 == k4
    assert k1 != k5


# -------------------------------------------------------------
# Test Case 6 — keyword-only args
# -------------------------------------------------------------

def kw_only(a, *, uid):
    return a + uid


def test_build_key_keyword_only():
    k1 = build(kw_only, 1, uid=9)
    k2 = build(kw_only, 1, uid=9)
    k3 = build(kw_only, 1, uid=10)
    k4 = build(kw_only, a=1, uid=9)
    assert k1 == k2
    assert k1 != k3
    assert k1 != k4


# -------------------------------------------------------------
# Test Case 7 — template string key_builder
# -------------------------------------------------------------

def get_user(uid, *, full=False):
    return uid


def test_build_key_template_builder():
    k1 = build(get_user, 123, full=True, key_builder="user:{uid}:full:{full}")

    # Should be callback
    k2 = build(get_user, 123, True, key_builder="user:{uid}:full:{full}")
    k3 = build(get_user, 123, True)

    # Call with args index
    k4 = build(get_user, 555, full=False, key_builder="user:{args[0]}")

    # Fallback to default builder
    k5 = build(get_user, uid=123, full=True, key_builder="ser:{args[0]}")

    assert k1 != k2
    assert k2 == k3
    assert "user:555" == k4
    assert k5 == "get_user:f261d842c3"


# -------------------------------------------------------------
# Test Case 8 — key_builder callable
# -------------------------------------------------------------

def test_build_key_callable_key_builder():
    def custom_builder(ctx, uid, full=False):
        return f"U:{uid}:F:{full}:FN:{ctx.qualname}"

    def custom_builder_raise(uid, full=False):
        raise ValueError("Forced failure")

    k1 = build(get_user, 555, full=False, key_builder=custom_builder)
    assert k1 == "U:555:F:False:FN:get_user"

    # Should fall back to default key builder
    k2 = build(get_user, 555, full=False, key_builder=custom_builder_raise)
    assert "get_user:" in k2


# -------------------------------------------------------------
# Test Case 9 — version appended
# -------------------------------------------------------------

def test_build_key_with_version():
    k = build(get_user, 1, full=True, version="v2")
    assert k.endswith("|v:v2")


# -------------------------------------------------------------
# Test Case 10 — Bound instance uniqueness (auto UUID)
# -------------------------------------------------------------

class Auto:
    def fn(self, x):
        return x


# -------------------------------------------------------------
# Test Case 11 — Ensure qualname dotted functions work
# -------------------------------------------------------------

def outer():
    def inner(a):
        return a

    return inner


def test_build_key_nested_function():
    fn = outer()
    k = build(fn, 10)
    assert k == "inner:1f28603384"


def test_build_key_with_class_in_args():
    class Dummy:
        pass

    def fn(x):
        return x

    k = build(fn, Dummy)  # class passed as positional arg
