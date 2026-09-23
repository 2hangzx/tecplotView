"""Equivalent to matlab/build_examples.m; produces reproducible previews."""
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from tecplot_viewer import demo_dataset, tecplot_cli, tecplot_plot


def build_examples(output_dir=None):
    out = Path(output_dir) if output_dir else Path(__file__).resolve().parent / "output"
    out.mkdir(parents=True, exist_ok=True)
    d = demo_dataset()
    figure = Figure(figsize=(14, 9), layout="constrained", facecolor="white")
    FigureCanvasAgg(figure)
    for n, (mode, variable, title) in enumerate([
        ("overlay", "Velocity", "Velocity + vectors (synthetic)"),
        ("contour", "Vorticity", "Vorticity contours (synthetic)"),
        ("streamlines", "Velocity", "Planar streamlines (synthetic)"),
        ("surface", "Velocity", "Scalar height surface (synthetic)"),
    ], 1):
        ax = figure.add_subplot(2, 2, n, projection="3d" if mode == "surface" else None)
        tecplot_plot(d, axes=ax, mode=mode, variable=variable, stride=6)
        ax.set_title(title)
    figure.savefig(out / "demo_overview.png", dpi=150)
    figure.clear()
    tecplot_cli(d, out / "velocity.png", variable="Velocity", clim=(0, .06))
    tecplot_cli(d, out / "vorticity.pdf", mode="contour", variable="Vorticity")
    print(f"Demo artifacts: {out}")


if __name__ == "__main__":
    build_examples()
