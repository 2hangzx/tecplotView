"""Resolve variables while retaining the original unit-bearing labels."""
from numbers import Integral
import re

from .models import TecplotError


def tecplot_variable(variables, selection: str | int, required: bool = True) -> int | None:
    """Return a zero-based column index. Numeric selections are ONE-based.

    Name matching is case insensitive, exact first, then with units removed.
    Ambiguous names always fail; a missing optional name returns None.
    """
    if isinstance(selection, Integral) and not isinstance(selection, bool):
        if 1 <= selection <= len(variables):
            return int(selection) - 1
        raise TecplotError("Variable", f"Column number must be between 1 and {len(variables)}.")
    if not isinstance(selection, str):
        raise TecplotError("Variable", "Use a variable name or a one-based integer column number.")
    matches = [n for n, value in enumerate(variables) if value.casefold() == selection.casefold()]
    if not matches:
        matches = [n for n, value in enumerate(variables)
                   if re.split(r"\s*[\(\[]", value, maxsplit=1)[0].strip().casefold() == selection.strip().casefold()]
    if len(matches) > 1:
        raise TecplotError("Variable", f"Ambiguous variable {selection!r}; use its full name or column number.")
    if not matches and required:
        raise TecplotError("Variable", f"Variable {selection!r} not found. Available: {', '.join(variables)}")
    return matches[0] if matches else None
