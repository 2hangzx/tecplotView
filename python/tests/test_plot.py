import copy

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
import pytest

from tecplot_viewer import Dataset, TecplotError, Zone, tecplot_grid, tecplot_plot


@pytest.mark.parametrize("mode", ["heatmap", "contour", "quiver", "overlay", "streamlines", "surface", "mesh"])
def test_all_modes_and_masking(demo, mode):
    original = demo.zones[0].data.copy()
    result = tecplot_plot(demo, mode=mode, valid_flag_values=[1], stride=8)
    result.figure.canvas.draw()
    assert result.axes.get_children()
    mask = tecplot_grid(demo, "Flag")[:, :, 0] == 1
    np.testing.assert_array_equal(result.info["flag_mask"], mask)
    if result.info["scalar"] is not None:
        assert np.all(np.isnan(result.info["scalar"][~mask]))
        assert result.colorbar is not None
    else:
        assert result.colorbar is None
    np.testing.assert_array_equal(demo.zones[0].data, original)
    result.figure.clear()


def test_colorbar_limits_mask_preservation_and_reverse_y(demo):
    result = tecplot_plot(demo, variable="Vorticity", clim=(-1, 1), reverse_y=True)
    assert (result.colorbar.vmin, result.colorbar.vmax) == (-1, 1)
    assert result.axes.yaxis_inverted()
    assert np.all(result.info["flag_mask"])
    np.testing.assert_array_equal(result.info["scalar"], tecplot_grid(demo, "Vorticity")[:, :, 0])
    assert result.artist.norm.vmin == -1
    assert result.artist.norm.vmax == 1
    result.figure.clear()


@pytest.mark.parametrize("clim", [(1, 1), (2, 1), (np.nan, 1), (-1, np.inf), [1], [1, 2, 3]])
def test_bad_limits_do_not_clear_previous_plot(demo, clim):
    result = tecplot_plot(demo, mode="heatmap")
    children = tuple(result.axes.get_children())
    with pytest.raises(TecplotError, match="ColorLimits"):
        tecplot_plot(demo, figure=result.figure, clim=clim)
    assert tuple(result.axes.get_children()) == children
    result.figure.clear()


def test_repeat_axes_no_duplicate_colorbar(demo):
    result = tecplot_plot(demo, mode="heatmap")
    for mode in ("contour", "mesh", "overlay"):
        result = tecplot_plot(demo, axes=result.axes, mode=mode)
        assert len(result.figure.axes) == (1 if mode == "mesh" else 2)
    result.figure.clear()


def test_descending_nonuniform_and_curved_streams():
    x, y = np.meshgrid([0., .1, .4, 1.], [0., .2, .5, 1.])
    data = np.column_stack([x.ravel(), y.ravel(), (1 + x).ravel(), (y * .1).ravel()])
    d = Dataset("rectilinear", ("X", "Y", "U", "V"), [Zone("plane", 4, 4, 1, "POINT", data)])
    result = tecplot_plot(d, mode="streamlines")
    assert result.info["stream_resampled"]
    result.figure.canvas.draw()
    result.figure.clear()
    d.zones[0].data[:, :2] *= -1
    result = tecplot_plot(d, mode="streamlines")
    result.figure.canvas.draw()
    result.figure.clear()
    d.zones[0].data[1, 1] += .01
    with pytest.raises(TecplotError, match="StreamGrid"):
        tecplot_plot(d, mode="streamlines")


def test_scalar_without_velocity_and_constant_contour():
    d = Dataset("constant", ("X", "Y", "P"), [Zone("plane", 2, 2, 1, "POINT",
        np.array([[0., 0., 7.], [1., 0., 7.], [0., 1., 7.], [1., 1., 7.]]))])
    result = tecplot_plot(d, mode="contour", variable="P")
    np.testing.assert_array_equal(result.info["scalar"], np.full((2, 2), 7.))
    result.figure.canvas.draw()
    result.figure.clear()
    with pytest.raises(TecplotError, match="Variable"):
        tecplot_plot(d, mode="quiver")


def test_slice_speed_and_missing_w():
    x, y = np.meshgrid([0., 1.], [0., 1.])
    first = np.column_stack([x.ravel(), y.ravel(), np.full(4, 3), np.full(4, 4)])
    second = first.copy()
    second[:, 2:] *= 2
    d = Dataset("2 layers", ("X", "Y", "U", "V"), [Zone("plane", 2, 2, 2, "POINT", np.vstack([first, second]))])
    result = tecplot_plot(d, mode="heatmap", k_slice=2)
    np.testing.assert_array_equal(result.info["scalar"], np.full((2, 2), 10.))
    result.figure.clear()
    with pytest.raises(TecplotError):
        tecplot_plot(d, k_slice=3)


def test_invalid_coordinates_no_valid_data_and_figure_modes(demo):
    with pytest.raises(TecplotError, match="NoValidData"):
        tecplot_plot(demo, valid_flag_values=[-999])
    d = copy.deepcopy(demo)
    d.zones[0].data[0, 0] = np.nan
    with pytest.raises(TecplotError, match="Coordinates"):
        tecplot_plot(d)
    figure = Figure()
    FigureCanvasAgg(figure)
    ax = figure.add_subplot()
    with pytest.raises(TecplotError, match="Axes"):
        tecplot_plot(demo, axes=ax, mode="surface")


def test_color_saturation_not_data_clipping(demo):
    result = tecplot_plot(demo, mode="contour", variable="Vorticity", clim=(-.1, .1))
    assert np.nanmin(result.info["scalar"]) < -.7
    np.testing.assert_allclose(result.artist.to_rgba(-1), result.artist.cmap(0.0))
    np.testing.assert_allclose(result.artist.to_rgba(1), result.artist.cmap(1.0))
    assert (result.colorbar.vmin, result.colorbar.vmax) == (-.1, .1)
    result.figure.canvas.draw()
    result.figure.clear()
