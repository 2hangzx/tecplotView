"""Headless export equivalent to tecplot_cli.m."""
from .tecplot_plot import tecplot_plot


def tecplot_cli(input_file, output_file, **kwargs):
    """Render and export, then release the figure; return the plotted arrays."""
    if not output_file:
        raise ValueError("Specify an output filename.")
    if {"axes", "figure", "output"} & kwargs.keys():
        raise ValueError("tecplot_cli owns axes, figure and output.")
    result = tecplot_plot(input_file, **kwargs)
    try:
        result.save(output_file, dpi=kwargs.get("dpi", 300))
        return result.info
    finally:
        result.figure.clear()
