"""Install the built wheel into a temporary target and run outside the source tree."""
from pathlib import Path
import subprocess
import sys
import tempfile


def check_wheel():
    root = Path(__file__).resolve().parents[1]
    wheel = root / "dist" / "tecplot_dat_viewer-0.1.0-py3-none-any.whl"
    output = root / "output"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wheel-check-", dir=output) as directory:
        work = Path(directory).resolve()
        assert work.parent == output.resolve()  # Scope temporary cleanup to this workspace.
        target = work / "installed"
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(target), str(wheel)], check=True)
        subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("wheel_probe.py")), str(target), str(work)],
                       cwd=work, check=True)
    print("Wheel installation, packaged data, independent CLI and GUI checks passed.")


if __name__ == "__main__":
    check_wheel()
