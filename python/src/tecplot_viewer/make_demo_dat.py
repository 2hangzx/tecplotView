"""Same deterministic 153 x 79 synthetic PIV field as make_demo_dat.m."""
from pathlib import Path

import numpy as np

from .models import Dataset, Zone


def demo_dataset() -> Dataset:
    x, y = np.meshgrid(np.arange(253, 862, 4, dtype=float), np.arange(512, 825, 4, dtype=float))
    a, b = (x - 557) / 150, (y - 668) / 80
    e = np.exp(-(a**2 + b**2))
    u, v = .025 + .05 * b * e, -.035 * a * e
    zero = np.zeros_like(x)
    vorticity = -.035 / .150 * e * (1 - 2 * a**2) - .05 / .080 * e * (1 - 2 * b**2)
    flag = np.where((x - 680)**2 + (y - 710)**2 < 22**2, 0., 1.)
    fields = (x, y, zero, u, v, zero, np.hypot(u, v), vorticity, flag)
    data = np.column_stack([field.ravel(order="C") for field in fields])
    variables = ("X(mm)", "Y(mm)", "Z(mm)", "U(m/s)", "V(m/s)", "W(m/s)", "Velocity(m/s)", "Vorticity", "Flag")
    return Dataset("SYNTHETIC PIV DEMO - NOT MEASURED DATA", variables,
                   [Zone("ZONE 1", 153, 79, 1, "POINT", data)])


def make_demo_dat(filename: str | Path = "synthetic_piv.dat", *, overwrite=False) -> Path:
    """Write the MATLAB-equivalent five-line header and nine-column POINT data."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    d = demo_dataset()
    with path.open("w" if overwrite else "x", encoding="utf-8", newline="\n") as handle:
        handle.write(f'TITLE="{d.title}"\n')
        handle.write('VARIABLES=' + " ".join(f'"{name}"' for name in d.variables) + "\n")
        handle.write('ZONE T="ZONE 1"\nI=153, J=79, K=1, F=POINT\n')
        handle.write("DT=(" + " ".join(["DOUBLE"] * 9) + ")\n")
        np.savetxt(handle, d.zones[0].data, fmt="%.9g")
    return path
