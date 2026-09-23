"""Compare exported MATLAB arrays to the Python reader/grid/render inputs."""
import json
from pathlib import Path

import numpy as np

from tecplot_viewer import read_tecplot_dat, tecplot_grid, tecplot_plot


def compare():
    root = Path(__file__).resolve().parents[1]
    reference = root / "output" / "matlab_reference"
    data = read_tecplot_dat(root / "src" / "tecplot_viewer" / "data" / "synthetic_piv.dat")
    checks = {"data": data.zones[0].data}
    for name in ("X", "Y", "U", "V", "Velocity", "Vorticity", "Flag"):
        checks[name] = tecplot_grid(data, name)[:, :, 0]
    result = tecplot_plot(data, variable="speed", valid_flag_values=[1], clim=(0, .06))
    checks.update(masked_speed=result.info["scalar"], masked_u=result.info["u"], masked_v=result.info["v"])
    report = {}
    for name, actual in checks.items():
        expected = np.genfromtxt(reference / f"{name}.csv", delimiter=",")
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-14, equal_nan=True)
        report[name] = dict(shape=list(actual.shape), max_abs_error=float(np.nanmax(np.abs(actual - expected))))
    result.figure.clear()
    text = json.dumps(report, indent=2)
    (reference / "comparison.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    compare()
