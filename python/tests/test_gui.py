import numpy as np
import pytest

from tecplot_viewer import Dataset, TecplotError, Zone

pytestmark = pytest.mark.gui


@pytest.fixture(scope="module")
def tk_root(request):
    # Do not mask application bugs as unavailable GUI dependencies.
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
    except (ImportError, RuntimeError) as exc:
        if request.config.getoption("--require-gui"):
            pytest.fail(f"Tk/display is required: {exc}")
        pytest.skip(f"Tk/display unavailable: {exc}")
    except tk.TclError as exc:
        if request.config.getoption("--require-gui"):
            pytest.fail(f"Tk/display is required: {exc}")
        pytest.skip(f"Tk/display unavailable: {exc}")
    yield root
    root.destroy()


@pytest.fixture
def app(demo, tk_root):
    # One Tcl interpreter per process, with a fresh app window per test.
    import tkinter as tk
    window = tk.Toplevel(tk_root)
    import tecplot_viewer as package
    viewer = package.tecplot_viewer(demo, root=window, visible=False)
    assert callable(package.tecplot_viewer)
    try:
        yield viewer
    finally:
        viewer.close()


def test_manual_limits_callbacks_recovery_and_export(app, tmp_path):
    assert app.result.info["clim"] is not None
    assert str(app.controls["clim_min"]["state"]) == "disabled"
    app.values["auto_clim"].set(False)
    app.values["clim_min"].set("-2e-2")
    app.values["clim_max"].set("0.06")
    app.redraw()
    assert app.result.info["clim"] == (-.02, .06)
    assert (app.result.colorbar.vmin, app.result.colorbar.vmax) == (-.02, .06)
    app.values["variable"].set("8: Vorticity")
    app.values["colormap"].set("jet")
    app.redraw()
    assert app.result.info["clim"] == (-.02, .06)
    previous = app.result
    for text in ("0.06", "1", "nan", "oops"):
        app.values["clim_min"].set(text)
        app.redraw()
        assert app.result is previous
        assert app.status.get().startswith("错误")
        with pytest.raises(TecplotError):
            app.export(tmp_path / "stale.png")
    app.values["clim_min"].set("-0.02")
    app.values["mode"].set("速度箭头")
    app.redraw()
    assert str(app.controls["clim_min"]["state"]) == "disabled"
    assert app.result.colorbar is None
    app.values["mode"].set("填色等值线")
    app.redraw()
    assert app.result.info["clim"] == (-.02, .06)
    app.controls["auto_clim"].invoke()
    assert app.values["auto_clim"].get()
    assert app.result.info["clim"][0] < -.1
    np.testing.assert_allclose([float(app.values["clim_min"].get()), float(app.values["clim_max"].get())], app.result.info["clim"])
    out = app.export(tmp_path / "gui.png", dpi=80)
    assert out.is_file()


@pytest.mark.parametrize("label", ["云图 + 箭头", "彩色云图", "填色等值线", "速度箭头", "流线 + 云图", "标量曲面", "网格"])
def test_actual_gui_mode_switch_and_canvas_draw(app, label):
    app.values["mode"].set(label)
    app.controls["mode"].event_generate("<<ComboboxSelected>>")
    app.root.update()
    app.canvas.draw()
    assert len(app.figure.axes) == (1 if label in ("速度箭头", "网格") else 2)
    assert app.result.axes.name == ("3d" if label == "标量曲面" else "rectilinear")


def test_scalar_reload_and_missing_mapping(app):
    data = np.array([[0., 0., 7.], [1., 0., 7.], [0., 1., 7.], [1., 1., 7.]])
    scalar = Dataset("scalar", ("X", "Y", "P"), [Zone("plane", 2, 2, 1, "POINT", data)])
    app.load(scalar)
    assert app.dataset is scalar
    assert app.result.info["scalar_name"] == "P"
    assert app.values["mode"].get() == "彩色云图"
    assert app.values["auto_clim"].get()
    unknown = Dataset("rename", ("axis_one", "axis_two", "P"), scalar.zones)
    app.load(unknown)
    assert app.result is None
    app.values["x_variable"].set("1: axis_one")
    app.values["y_variable"].set("2: axis_two")
    app.redraw()
    assert app.result is not None
