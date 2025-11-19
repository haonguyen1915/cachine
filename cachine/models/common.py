from typing import NamedTuple, Optional


class KeyContext(NamedTuple):
    """Context passed to user key builders.

    Attributes:
        module (str): Module name containing the function.
        qualname (str): Qualified function name (may include class).
        full_name (str): Fully qualified path ``module.qualname``.
        version (str | None): Decorator version string, if provided.
    """

    module: str
    qualname: str
    full_name: str
    version: Optional[str]
