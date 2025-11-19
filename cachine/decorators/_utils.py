import hashlib
import inspect
import json
import logging
import re
import uuid
from collections.abc import Callable
from typing import Any, Optional

from cachine.models.common import KeyContext

PLACEHOLDER_RE = re.compile(r"{([^{}]+)}")
_logger = logging.getLogger(__name__)
# ================================================================
# Value Normalizer
# ================================================================

PRIMITIVE = (int, float, str, bool, type(None))


def normalize_value(v: Any) -> Any:
    """Convert ANY Python value into a stable, deterministic, JSON-friendly representation."""

    # Primitive types → leave unchanged
    if isinstance(v, PRIMITIVE):
        return v

    # Class object
    if inspect.isclass(v):
        return f"class:{v.__module__}.{v.__qualname__}"

    # Function / method
    if inspect.isfunction(v) or inspect.ismethod(v):
        q = getattr(v, "__qualname__", v.__name__).replace(".<locals>", "")
        return f"fn:{v.__module__}.{q}"

    # Instance with custom cache key
    if hasattr(v, "__cache_key__") and callable(v.__cache_key__):
        try:
            return f"inst:{v.__cache_key__()}"
        except Exception:
            pass

    if hasattr(v, "cache_key"):
        try:
            key_attr = v.cache_key
            return f"inst:{key_attr() if callable(key_attr) else key_attr}"
        except Exception:
            pass

    # Fallback: persistent per-instance UUID
    inst_id = getattr(v, "__cachine_id", None)
    if not inst_id:
        inst_id = uuid.uuid4().hex
        try:
            setattr(v, "__cachine_id", inst_id)
        except Exception:
            pass

    return f"inst:{inst_id}"


# ================================================================
# Hash Builder
# ================================================================


def hash_components(func_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Compute a deterministic, compact SHA256 hash from normalized arguments."""
    payload = json.dumps(
        {
            "fn": func_name,
            "args": [normalize_value(v) for v in args],
            "kwargs": {k: normalize_value(v) for k, v in kwargs.items()},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:10]


# ================================================================
# Unified Key Builder (public)
# ================================================================


def build_cache_key(
    fn: Callable[..., Any],
    key_builder: Optional[str | Callable[..., str]],
    version: Optional[str],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    """
    SINGLE SOURCE OF TRUTH for all cache keys.

    Order:
        1. Template string builder
        2. Callable builder
        3. Deterministic hash fallback
    """

    module = fn.__module__
    qualname = getattr(fn, "__qualname__", fn.__name__).replace(".<locals>", "")
    func_name = f"{module}.{qualname}"

    context = KeyContext(
        module=module,
        qualname=qualname,
        full_name=func_name,
        version=version,
    )

    # -----------------------------------------------------------
    # 1. TEMPLATE MODE
    # -----------------------------------------------------------
    if isinstance(key_builder, str):
        tmpl = template_key_builder(key_builder)

        # Resolve argument mapping
        try:
            sig = inspect.signature(fn)
            ba = sig.bind_partial(*args, **kwargs)
            ba.apply_defaults()
            bound_kwargs = dict(ba.arguments)
        except Exception:
            bound_kwargs = dict(kwargs)

        key = None

        # Try with ctx
        try:
            key = tmpl(context, *args, **bound_kwargs)
        except Exception:
            pass

        # Try without ctx
        if key is None:
            try:
                key = tmpl(*args, **bound_kwargs)
            except Exception:
                key = None

        if key is not None:
            return f"{key}|v:{version}" if version else key
        else:
            _logger.warning(f"Falling back to hash-based cache key for function {func_name}")

        # Template failed → continue to hash fallback

    # -----------------------------------------------------------
    # 2. CALLABLE builder
    # -----------------------------------------------------------
    if callable(key_builder):
        key = None

        try:
            key = key_builder(context, *args, **kwargs)
        except Exception:
            pass

        if key is None:
            try:
                key = key_builder(*args, **kwargs)
            except Exception:
                key = None

        if key is not None:
            return f"{key}|v:{version}" if version else key
        else:
            _logger.warning(f"Falling back to hash-based cache key for function {func_name}")

        # Callable builder failed → continue to hash fallback

    # -----------------------------------------------------------
    # 3. DEFAULT HASH MODE (always consistent)
    # -----------------------------------------------------------
    h = hash_components(func_name, args, kwargs)
    short_name = qualname.split(".")[-1]
    final_key = f"{short_name}:{h}"

    return f"{final_key}|v:{version}" if version else final_key


def template_key_builder(template: str) -> Callable[..., Optional[str]]:
    """
    Compile a template string into a safe key builder.

    Supported patterns:
        {uid}
        {id}
        {ctx.module}
        {ctx.full_name}
        {args[0]}
        {kwargs.user_id}

    Rules:
        - Nếu bất kỳ placeholder nào không resolve được -> trả None để fallback sang hash.
        - Giá trị được normalize bằng normalize_value().
        - Không raise exception ra ngoài (chỉ trả None).
    """

    placeholders = PLACEHOLDER_RE.findall(template)

    def build(*call_args, **call_kwargs) -> Optional[str]:
        """
        Gọi theo một trong hai dạng:
            tmpl(ctx, *args, **kwargs)
            tmpl(*args, **kwargs)

        ctx detection:
            - Nếu call_args[0] có attr full_name & module -> coi là KeyContext.
        """
        if not placeholders:
            return template

        ctx = None
        args = ()
        kwargs = call_kwargs

        if call_args:
            first = call_args[0]
            if hasattr(first, "full_name") and hasattr(first, "module"):
                ctx = first
                args = call_args[1:]
            else:
                args = call_args

        result = template
        missing_any = False  # flag để quyết định fallback

        try:
            for ph in placeholders:
                value: Any = None
                resolved = False

                # ctx.xxx
                if ctx and ph.startswith("ctx."):
                    attr = ph.split("ctx.", 1)[1]
                    if hasattr(ctx, attr):
                        value = getattr(ctx, attr)
                        resolved = True

                # args[i]
                elif ph.startswith("args["):
                    try:
                        idx = int(ph[5:-1])
                        if 0 <= idx < len(args):
                            value = args[idx]
                            resolved = True
                    except Exception:
                        pass

                # kwargs.xxx
                elif ph.startswith("kwargs."):
                    key = ph.split("kwargs.", 1)[1]
                    if key in kwargs:
                        value = kwargs[key]
                        resolved = True

                # simple {key} -> ưu tiên kwargs
                else:
                    if ph in kwargs:
                        value = kwargs[ph]
                        resolved = True

                if not resolved:
                    # Không resolve được placeholder -> đánh dấu fail
                    missing_any = True
                    # Không thay thế placeholder này, để cuối cùng phát hiện vẫn còn {..}
                    continue

                # Normalize + stringify
                value = normalize_value(value)
                result = result.replace("{" + ph + "}", "" if value is None else str(value))

            # Nếu còn placeholder chưa được thay hoặc flag missing → coi như thất bại
            if missing_any or "{" in result or "}" in result:
                return None

            return result

        except Exception:
            return None

    return build
