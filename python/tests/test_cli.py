import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

from tecplot_viewer import tecplot_cli


def command(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "tecplot_viewer", *map(str, args)],
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def test_cli_inspect_and_module_entry(sample, tmp_path):
    result = command("inspect", sample, "--json", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    metadata = json.loads(result.stdout)
    assert metadata["zones"][0]["points"] == 12087
    assert len(metadata["variables"]) == 9
    assert metadata["zones"][0]["solution_time"] is None


def test_installed_console_script(tmp_path):
    script = Path(sys.executable).parent / ("tecplot-viewer.exe" if sys.platform == "win32" else "tecplot-viewer")
    result = subprocess.run([str(script), "--version"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "0.1.0" in result.stdout


@pytest.mark.parametrize("extension", ["png", "pdf", "svg", "jpg"])
def test_export_formats(sample, tmp_path, extension):
    path = tmp_path / f"plot.{extension}"
    info = tecplot_cli(sample, path, mode="contour", variable="Vorticity", clim=(-1., 1.), dpi=100)
    assert path.stat().st_size > 1000
    assert info["clim"] == (-1, 1)
    if extension == "png":
        with Image.open(path) as image:
            assert image.width > 500


def test_cli_plot_and_error_exit_codes(sample, tmp_path):
    image = tmp_path / "cli.png"
    good = command("plot", sample, "-o", image, "--clim", "0", "0.06", "--dpi", "80", cwd=tmp_path)
    assert good.returncode == 0, good.stderr
    assert image.is_file()
    bad = command("plot", sample, "-o", image, "--clim", "1", "0", cwd=tmp_path)
    assert bad.returncode == 2
    assert "ColorLimits" in bad.stderr
    assert "Traceback" not in bad.stderr
    missing = command("inspect", tmp_path / "missing.dat", cwd=tmp_path)
    assert missing.returncode == 2


def test_cli_demo_guard_and_malformed_arguments(tmp_path):
    path = tmp_path / "generated.dat"
    assert command("demo", path).returncode == 0
    assert command("demo", path).returncode == 2
    assert command("demo", path, "--overwrite").returncode == 0
    assert command("plot", path, "-o", "bad.png", "--stride", "0").returncode == 2


def test_headless_import_does_not_load_tk(tmp_path):
    result = subprocess.run([sys.executable, "-c", "import sys; import tecplot_viewer; assert 'tkinter' not in sys.modules"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
