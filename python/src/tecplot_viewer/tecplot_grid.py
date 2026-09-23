"""Restore I-fastest node rows as [J, I, K] arrays."""
from numbers import Integral

import numpy as np

from .models import Dataset, TecplotError
from .tecplot_variable import tecplot_variable


def positive_integer(value, name: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1 or (maximum is not None and value > maximum):
        raise TecplotError("Option", f"{name} must be a positive integer" + (f" <= {maximum}." if maximum else "."))
    return int(value)


def tecplot_grid(dataset: Dataset, variable: str | int, zone: int = 1) -> np.ndarray:
    """Return shape (J,I,K), including the singleton K dimension.

    Arguments zone and numeric variable are one-based like the MATLAB API;
    the returned NumPy array uses ordinary zero-based indexing.
    """
    index = positive_integer(zone, "zone", len(dataset.zones)) - 1
    column = tecplot_variable(dataset.variables, variable)
    z = dataset.zones[index]
    return z.data[:, column].reshape((z.k, z.j, z.i)).transpose(1, 2, 0)
