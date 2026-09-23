"""Tecplot ASCII/PIV reader, renderer, CLI and optional Tk viewer."""
from .models import Dataset, TecplotError, Zone
from .read_tecplot_dat import read_tecplot_dat
from .tecplot_grid import tecplot_grid
from .tecplot_variable import tecplot_variable
from .tecplot_plot import tecplot_plot, PlotResult
from .tecplot_cli import tecplot_cli
from .make_demo_dat import make_demo_dat, demo_dataset

__version__ = "0.1.0"


def tecplot_viewer(filename=None, **kwargs):
    """Create a Tk desktop viewer; import Tk only when this function is used."""
    from .gui import TecplotViewer
    return TecplotViewer(filename, **kwargs)


__all__ = ["Dataset", "Zone", "TecplotError", "PlotResult", "read_tecplot_dat",
           "tecplot_variable", "tecplot_grid", "tecplot_plot", "tecplot_cli",
           "tecplot_viewer", "make_demo_dat", "demo_dataset"]
