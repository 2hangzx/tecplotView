"""Data containers; raw rows retain Tecplot's I-fastest node order."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np


class TecplotError(ValueError):
    """An invalid input or an explicitly unsupported Tecplot feature."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass
class Zone:
    name: str
    i: int
    j: int
    k: int
    packing: str
    data: np.ndarray
    solution_time: float = float("nan")
    strand_id: int | None = None
    header: str = ""


@dataclass
class Dataset:
    title: str
    variables: tuple[str, ...]
    zones: list[Zone]
    filename: Path | None = None
    format: str = "Tecplot ASCII ordered nodal"
