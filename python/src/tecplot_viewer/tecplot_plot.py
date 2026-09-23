"""Matplotlib equivalent of the seven tecplot_plot.m rendering modes."""
from dataclasses import dataclass
from pathlib import Path
import re

import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import Colormap, ListedColormap, Normalize
from matplotlib.figure import Figure
import numpy as np

from .models import Dataset, TecplotError
from .read_tecplot_dat import read_tecplot_dat
from .tecplot_grid import positive_integer, tecplot_grid
from .tecplot_variable import tecplot_variable

MODES = ("heatmap", "contour", "quiver", "overlay", "streamlines", "surface", "mesh")


@dataclass
class PlotResult:
    figure: Figure
    axes: object
    info: dict
    colorbar: object = None
    artist: object = None

    def __iter__(self):
        """Allow fig, ax, info = tecplot_plot(...) just like the MATLAB port."""
        yield self.figure
        yield self.axes
        yield self.info

    def save(self, filename: str | Path, *, dpi: int = 300):
        positive_integer(dpi, "dpi")
        path = Path(filename)
        if path.suffix.lower() not in {".png", ".pdf", ".jpg", ".jpeg", ".svg", ".tif", ".tiff"}:
            raise TecplotError("Output", "Use PNG/PDF/JPEG/SVG/TIFF for the output filename.")
        self.figure.savefig(path, dpi=dpi, facecolor="white", bbox_inches="tight")
        return path


def _stream_grid(x, y, u, v):
    xv, yv = x[0, :], y[:, 0]
    if (not np.allclose(x, xv[None, :], rtol=0, atol=max(1, np.max(np.abs(x))) * 1e-9)
            or not np.allclose(y, yv[:, None], rtol=0, atol=max(1, np.max(np.abs(y))) * 1e-9)):
        raise TecplotError("StreamGrid", "Streamlines require a rectilinear XY grid; use overlay for a curved grid.")
    if np.all(np.diff(xv) < 0):
        xv, u, v = xv[::-1], u[:, ::-1], v[:, ::-1]
    if np.all(np.diff(yv) < 0):
        yv, u, v = yv[::-1], u[::-1, :], v[::-1, :]
    if np.any(np.diff(xv) <= 0) or np.any(np.diff(yv) <= 0):
        raise TecplotError("StreamGrid", "X/Y must be strictly monotonic with no duplicate positions.")
    # Matplotlib's streamplot requires uniform spacing. Resample only its
    # velocity input, using separable linear interpolation. NaN gaps remain.
    resampled = not (np.allclose(np.diff(xv), np.diff(xv)[0], rtol=1e-7, atol=0)
                     and np.allclose(np.diff(yv), np.diff(yv)[0], rtol=1e-7, atol=0))
    if resampled:
        newx, newy = np.linspace(xv[0], xv[-1], len(xv)), np.linspace(yv[0], yv[-1], len(yv))

        def resample(field):
            rows = np.array([np.interp(newx, xv, row) for row in field])
            return np.array([np.interp(newy, yv, column) for column in rows.T]).T

        u, v = resample(u), resample(v)
        xv, yv = newx, newy
    return xv, yv, u, v, resampled


def _colormap(value):
    if isinstance(value, Colormap):
        return value
    if isinstance(value, str):
        try:
            return matplotlib.colormaps[value]
        except KeyError as exc:
            raise TecplotError("Colormap", f"Unknown Matplotlib colormap {value!r}; try viridis/turbo/jet.") from exc
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or array.shape[1] != 3 or not len(array) or not np.all(np.isfinite(array)) or np.any((array < 0) | (array > 1)):
        raise TecplotError("Colormap", "A custom colormap must be a finite N x 3 RGB array in [0,1].")
    return ListedColormap(array)


def tecplot_plot(source: str | Path | Dataset, *, mode="overlay", variable="speed",
                 zone=1, k_slice=1, axes=None, figure=None, output=None, dpi=300,
                 levels=24, stride=5, vector_scale=1.2, clim=None, colormap="viridis",
                 reverse_y=False, valid_flag_values=None, x_variable="X", y_variable="Y",
                 u_variable="U", v_variable="V", w_variable="W", flag_variable="Flag") -> PlotResult:
    """Render a K plane; see README for the MATLAB-to-Python option mapping.

    No GUI or pyplot backend is initialized here. A standalone result can be
    saved on a headless host. Pass axes=... for notebook/subplot embedding, or
    figure=... for a desktop viewer that owns the complete figure.
    """
    if mode not in MODES:
        raise TecplotError("Mode", f"mode must be one of {', '.join(MODES)}.")
    positive_integer(levels, "levels")
    if levels < 2:
        raise TecplotError("Option", "levels must be at least 2.")
    positive_integer(stride, "stride")
    positive_integer(dpi, "dpi")
    if not np.isscalar(vector_scale) or not np.isreal(vector_scale) or not np.isfinite(vector_scale) or vector_scale < 0:
        raise TecplotError("Option", "vector_scale must be finite and nonnegative.")
    if clim is not None:
        bounds = np.asarray(clim, dtype=float)
        if bounds.shape != (2,) or not np.all(np.isfinite(bounds)) or bounds[0] >= bounds[1]:
            raise TecplotError("ColorLimits", "clim needs finite [lower, upper] with lower < upper.")
    else:
        bounds = None
    cmap = _colormap(colormap)
    d = read_tecplot_dat(source) if isinstance(source, (str, Path)) else source
    if not isinstance(d, Dataset):
        raise TypeError("source must be a DAT path or Dataset")
    z = d.zones[positive_integer(zone, "zone", len(d.zones)) - 1]
    positive_integer(k_slice, "k_slice", z.k)
    if z.i < 2 or z.j < 2:
        raise TecplotError("PlotDimensions", "XY rendering needs I >= 2 and J >= 2.")

    def plane(selection):
        return tecplot_grid(d, selection, zone)[:, :, k_slice - 1].copy()

    xi, yi = tecplot_variable(d.variables, x_variable), tecplot_variable(d.variables, y_variable)
    x, y = plane(xi + 1), plane(yi + 1)
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)) or np.ptp(x) == 0 or np.ptp(y) == 0:
        raise TecplotError("Coordinates", "Finite X/Y coordinates must span both dimensions.")
    flag_mask = np.ones(x.shape, dtype=bool)
    if valid_flag_values is not None:
        values = np.asarray(valid_flag_values, dtype=float).reshape(-1)
        if not np.all(np.isfinite(values)):
            raise TecplotError("Option", "valid_flag_values must be finite.")
        if values.size:
            flag_mask = np.isin(plane(flag_variable), values)
    need_vectors = mode in {"quiver", "overlay", "streamlines"}
    need_scalar = mode not in {"quiver", "mesh"}
    speed = isinstance(variable, str) and variable.casefold() == "speed"
    u = v = scalar = None
    scalar_name = ""
    if need_vectors or (need_scalar and speed):
        u, v = plane(u_variable), plane(v_variable)
    if need_scalar:
        if speed:
            wi = tecplot_variable(d.variables, w_variable, required=False)
            w = np.zeros_like(u) if wi is None else plane(wi + 1)
            scalar = np.hypot(np.hypot(u, v), w)
            ui = tecplot_variable(d.variables, u_variable)
            units = re.search(r"(\([^)]*\)|\[[^]]*\])\s*$", d.variables[ui])
            scalar_name = "Speed" + (" " + units[1] if units else "")
        else:
            ci = tecplot_variable(d.variables, variable)
            scalar, scalar_name = plane(ci + 1), d.variables[ci]
        scalar[~flag_mask | ~np.isfinite(scalar)] = np.nan
        if not np.any(np.isfinite(scalar)):
            raise TecplotError("NoValidData", "No finite scalar values remain after filtering.")
        if bounds is None:
            bounds = np.array([np.nanmin(scalar), np.nanmax(scalar)])
            if bounds[0] == bounds[1]:
                padding = max(abs(bounds[0]) * .01, 1e-12) if bounds[0] else 1.0
                bounds = bounds + np.array([-padding, padding])
    if need_vectors:
        invalid = ~flag_mask | ~np.isfinite(u) | ~np.isfinite(v)
        u[invalid] = v[invalid] = np.nan
        if not np.any(np.isfinite(u)):
            raise TecplotError("NoValidData", "No finite vectors remain after filtering.")
    stream = _stream_grid(x, y, u, v) if mode == "streamlines" else None
    if axes is not None and figure is not None:
        raise TecplotError("Axes", "Specify axes or figure, not both.")
    if axes is not None and ((mode == "surface") != (axes.name == "3d")):
        raise TecplotError("Axes", "surface requires 3D axes; all other modes require 2D axes.")
    # Validation is complete before mutating an existing plot.
    if axes is None:
        if figure is None:
            figure = Figure(figsize=(10, 6.4), layout="constrained", facecolor="white")
            FigureCanvasAgg(figure)
        else:
            figure.clear()
        ax = figure.add_subplot(111, projection="3d" if mode == "surface" else None)
    else:
        ax, figure = axes, axes.figure
        previous = getattr(ax, "_tecplot_colorbar", None)
        if previous is not None:
            previous.remove()
        ax.clear()
    ax._tecplot_colorbar = None
    norm = Normalize(*bounds, clip=True) if need_scalar else None
    artist = None
    if mode in {"heatmap", "streamlines"}:
        artist = ax.pcolormesh(x, y, np.ma.masked_invalid(scalar), cmap=cmap, norm=norm, shading="gouraud")
    elif mode in {"contour", "overlay"}:
        if np.nanmin(scalar) == np.nanmax(scalar):
            artist = ax.pcolormesh(x, y, scalar, cmap=cmap, norm=norm, shading="nearest")
        else:
            # Levels span the chosen colorbar limits; values outside saturate
            # to endpoint colors without changing the source scalar values.
            artist = ax.contourf(x, y, scalar, levels=np.linspace(*bounds, levels + 1),
                                 cmap=cmap, norm=norm, extend="both", corner_mask=False)
    elif mode == "surface":
        artist = ax.plot_surface(x, y, scalar, cmap=cmap, norm=norm, linewidth=0,
                                 rcount=z.j, ccount=z.i, antialiased=True)
        ax.set_zlabel(scalar_name)
    elif mode == "mesh":
        mx, my = np.where(flag_mask, x, np.nan), np.where(flag_mask, y, np.nan)
        ax.plot(mx, my, color="#335977", linewidth=.45)
        ax.plot(mx.T, my.T, color="#335977", linewidth=.45)
    if mode in {"quiver", "overlay"}:
        xs, ys, us, vs = (a[::stride, ::stride] for a in (x, y, u, v))
        if vector_scale:
            # Scale the longest arrow to vector_scale times the typical
            # sampled spacing. This matches the intent, not MATLAB pixels.
            spacing = [np.hypot(np.diff(xs, axis=1), np.diff(ys, axis=1)).ravel(),
                       np.hypot(np.diff(xs, axis=0), np.diff(ys, axis=0)).ravel()]
            distances = np.concatenate(spacing)
            distances = distances[distances > 0]
            spacing_value = np.median(distances) if distances.size else min(np.ptp(x), np.ptp(y))
            magnitude = np.hypot(us, vs)
            maximum = np.max(magnitude[np.isfinite(magnitude)], initial=0)
            factor = vector_scale * spacing_value / maximum if maximum else 1
        else:
            factor = 1  # Literal velocity-component lengths in coordinate units.
        arrows = ax.quiver(xs, ys, us * factor, vs * factor, angles="xy", scale_units="xy",
                           scale=1, color="#202020", width=.0025, zorder=3)
        if artist is None:
            artist = arrows
    elif stream is not None:
        sx, sy, su, sv, _ = stream
        ax.streamplot(sx, sy, np.ma.masked_invalid(su), np.ma.masked_invalid(sv),
                      density=float(np.clip(6 / stride, .4, 2.5)), color="#202020",
                      linewidth=.7, arrowsize=.8, zorder=3)
    cb = None
    if need_scalar:
        # Independent ScalarMappable keeps the colorbar continuous with
        # exact requested limits, even when the field has constant values.
        cb = figure.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, pad=.035)
        cb.set_label(scalar_name)
        ax._tecplot_colorbar = cb
    ax.set(xlabel=d.variables[xi], ylabel=d.variables[yi], xlim=(x.min(), x.max()), ylim=(y.min(), y.max()))
    if mode != "surface":
        ax.set_aspect("equal", adjustable="box")
    if reverse_y:
        ax.invert_yaxis()
    title = " | ".join(part for part in (d.title, z.name, scalar_name) if part)
    if z.k > 1:
        title += f" | K = {k_slice}"
    if np.isfinite(z.solution_time):
        title += f" | t = {z.solution_time:g}"
    ax.set_title(title, fontsize=10)
    info = dict(zone=zone, k_slice=k_slice, mode=mode, x=x, y=y, scalar=scalar, u=u, v=v,
                flag_mask=flag_mask, scalar_name=scalar_name,
                clim=tuple(bounds) if need_scalar else None,
                stream_resampled=stream[-1] if stream else False)
    result = PlotResult(figure, ax, info, cb, artist)
    if output is not None:
        result.save(output, dpi=dpi)
    return result
