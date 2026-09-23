from pathlib import Path
from importlib.resources import files

import pytest

from tecplot_viewer import demo_dataset


def pytest_addoption(parser):
    parser.addoption("--require-gui", action="store_true", help="Fail instead of skipping if Tk/display is unavailable")


@pytest.fixture
def demo():
    return demo_dataset()


@pytest.fixture
def sample():
    return Path(str(files("tecplot_viewer").joinpath("data/synthetic_piv.dat")))


@pytest.fixture
def dat_file(tmp_path):
    def write(text, name="input.dat"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path
    return write
