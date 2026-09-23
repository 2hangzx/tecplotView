"""Equivalent to matlab/run_demo.m; install this package first."""
from tecplot_viewer import demo_dataset, tecplot_viewer

if __name__ == "__main__":
    tecplot_viewer(demo_dataset()).run()
