"""Installed tecplot-viewer command and python -m tecplot_viewer."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

from .make_demo_dat import demo_dataset, make_demo_dat
from .read_tecplot_dat import read_tecplot_dat
from .tecplot_cli import tecplot_cli
from .tecplot_plot import MODES


def _selection(text):
    return int(text) if text.isdecimal() else text


def parser():
    result = argparse.ArgumentParser(description="Tecplot ASCII/PIV viewer: GUI, headless plotting and inspection.")
    result.add_argument("--version", action="version", version="tecplot-dat-viewer 0.1.0")
    commands = result.add_subparsers(dest="command", required=True)
    gui = commands.add_parser("gui", help="Open the desktop viewer")
    gui.add_argument("file", nargs="?", type=Path)
    gui.add_argument("--demo", action="store_true", help="Load synthetic PIV data")
    inspect = commands.add_parser("inspect", help="Validate and describe a DAT file")
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--json", action="store_true", help="Print machine-readable metadata")
    demo = commands.add_parser("demo", help="Write a synthetic 153 x 79, nine-variable DAT file")
    demo.add_argument("file", nargs="?", default=Path("synthetic_piv.dat"), type=Path)
    demo.add_argument("--overwrite", action="store_true")
    plot = commands.add_parser("plot", help="Render and export without a display")
    plot.add_argument("file", type=Path)
    plot.add_argument("-o", "--output", required=True, type=Path)
    plot.add_argument("--mode", choices=MODES, default="overlay")
    plot.add_argument("--variable", type=_selection, default="speed", help="Name / one-based column, or speed to calculate magnitude")
    plot.add_argument("--zone", type=int, default=1, help="One-based zone number")
    plot.add_argument("--k-slice", type=int, default=1)
    plot.add_argument("--levels", type=int, default=24)
    plot.add_argument("--stride", type=int, default=5)
    plot.add_argument("--vector-scale", type=float, default=1.2)
    plot.add_argument("--clim", type=float, nargs=2, metavar=("LOWER", "UPPER"))
    plot.add_argument("--colormap", default="viridis")
    plot.add_argument("--valid-flags", type=float, nargs="+", dest="valid_flag_values")
    plot.add_argument("--reverse-y", action="store_true")
    plot.add_argument("--dpi", type=int, default=300)
    for letter in ("x", "y", "u", "v", "w", "flag"):
        plot.add_argument(f"--{letter}-variable", type=_selection, default=letter.upper() if letter != "flag" else "Flag")
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "gui":
            if args.demo and args.file:
                raise ValueError("Choose a file or --demo, not both.")
            try:
                from .gui import TecplotViewer
            except ImportError as exc:
                raise ValueError("GUI requires Python with tkinter/Tcl/Tk; headless plot does not.") from exc
            app = TecplotViewer(demo_dataset() if args.demo else args.file)
            app.run()
        elif args.command == "demo":
            print(make_demo_dat(args.file, overwrite=args.overwrite))
        elif args.command == "plot":
            options = vars(args).copy()
            del options["command"]
            source, output = options.pop("file"), options.pop("output")
            tecplot_cli(source, output, **options)
            print(f"Exported: {output}")
        else:
            d = read_tecplot_dat(args.file)
            metadata = dict(title=d.title, variables=d.variables, format=d.format, zones=[
                dict(name=z.name, i=z.i, j=z.j, k=z.k, packing=z.packing, points=len(z.data),
                     solution_time=z.solution_time if np.isfinite(z.solution_time) else None,
                     strand_id=z.strand_id) for z in d.zones])
            if args.json:
                print(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False))
            else:
                print(f"{d.title}\n{len(d.variables)} variables: {', '.join(d.variables)}")
                for n, z in enumerate(d.zones, 1):
                    print(f"Zone {n}: {z.name} | {z.i} x {z.j} x {z.k} | {z.packing} | {len(z.data)} points")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
