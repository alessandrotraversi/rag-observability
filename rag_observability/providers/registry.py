"""Name -> factory registry with a dotted-path escape hatch ("pkg.module:Class")."""

import importlib
from typing import Any, Callable

from rag_observability.core.errors import ConfigurationError


def resolve(kind: str, name: str, builtins: dict[str, Callable[..., Any]]) -> Callable[..., Any]:
    if name in builtins:
        return builtins[name]
    if ":" in name:
        module_name, _, attribute = name.partition(":")
        try:
            return getattr(importlib.import_module(module_name), attribute)
        except (ImportError, AttributeError) as exc:
            raise ConfigurationError(f"cannot load {kind} '{name}': {exc}") from exc
    known = ", ".join(sorted(builtins))
    raise ConfigurationError(
        f"unknown {kind} '{name}'. Use one of: {known}, or 'package.module:Factory'."
    )
