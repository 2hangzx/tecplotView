"""Child process for check_wheel.py; run with Python isolated mode (-I)."""
from pathlib import Path
import sys

target, work = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
sys.path.insert(0, str(target))

import tecplot_viewer  # noqa: E402
from tecplot_viewer.cli import main  # noqa: E402
from tecplot_viewer.gui import TecplotViewer  # noqa: E402

assert Path(tecplot_viewer.__file__).resolve().is_relative_to(target)
sample = target / "tecplot_viewer" / "data" / "synthetic_piv.dat"
assert sample.is_file()
assert main(["inspect", str(sample)]) == 0
assert main(["plot", str(sample), "-o", str(work / "wheel.png"), "--clim", "0", ".06", "--dpi", "80"]) == 0
assert (work / "wheel.png").stat().st_size > 1000
app = TecplotViewer(sample, visible=False)
try:
    app.canvas.draw()
    assert app.result.info["scalar_name"] == "Velocity(m/s)"
finally:
    app.close()
