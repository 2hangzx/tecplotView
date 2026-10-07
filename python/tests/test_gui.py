import numpy as np
import pytest
import time

from tecplot_viewer import Dataset, TecplotError, Zone

pytestmark = pytest.mark.gui


@pytest.fixture
def collection(tmp_path):
    header = 'VARIABLES="X" "Y" "U" "V" "Velocity" "Flag"\nZONE I=2,J=2,F=POINT\n'
    rows = "0 0 1 0 1 1\n1 0 1 0 1 1\n0 1 1 0 1 1\n1 1 1 0 1 1\n"
    (tmp_path / "file2.dat").write_text(header + rows, encoding="utf-8")
    # Variable order changes; restoration must use names, never old column numbers.
    swapped = 'VARIABLES="Y" "X" "V" "U" "Flag" "Velocity"\nZONE I=2,J=2,F=POINT\n'
    (tmp_path / "file10.dat").write_text(swapped + "0 0 0 2 1 2\n0 1 0 2 1 2\n1 0 0 2 1 2\n1 1 0 2 1 2\n", encoding="utf-8")
    return tmp_path


def finish_scan(app):
    deadline = time.monotonic() + 5
    while app._scan_id is not None and time.monotonic() < deadline:
        app.root.update()
    assert app._scan_id is None


def test_folder_manual_navigation_preserves_settings_by_name(app, collection):
    old = app.dataset
    app.scan_folder(collection)
    finish_scan(app)
    assert app.dataset is old  # Discovery does not assume a time series or load a file.
    assert app.sequence.current is None
    records = app.sequence.ordered()
    assert [item.relative_path for item in records] == ["file2.dat", "file10.dat"]
    app.files_tree.focus("file2.dat")
    app.files_tree.selection_set("file2.dat")
    app.root.update()
    assert app.sequence.current == "file2.dat"
    app.values["clim_min"].set("0")
    app.values["clim_max"].set("3")
    app.values["auto_clim"].set(False)
    app.values["flags"].set("1")
    app.redraw()
    app.step_file()
    assert app.sequence.current == "file10.dat"
    assert app.values["variable"].get() == "6: Velocity"
    assert app.values["x_variable"].get() == "2: X"
    assert app.values["u_variable"].get() == "4: U"
    assert app.values["flags"].get() == "1"
    assert app.result.info["clim"] == (0, 3)
    app.order.set("倒序")
    app._browser_option_changed()
    app.step_file()
    assert app.sequence.current == "file2.dat"


def test_real_scheduled_playback_end_loop_pause_and_close(app, collection):
    app.scan_folder(collection)
    finish_scan(app)
    app.interval.set("0.005")
    app.play()
    deadline = time.monotonic() + 5
    while app._playing and time.monotonic() < deadline:
        app.root.update()
    assert not app._playing
    assert app.sequence.current == "file10.dat"
    assert "播放结束" in app.status.get()
    app.loop.set(True)
    app.play()
    assert app._play_id is not None
    app.root.after_cancel(app._play_id)
    app._play_tick()
    assert app.sequence.current == "file2.dat"
    assert app._playing
    app.pause()
    assert app._play_id is None
    app.play()
    app.close()
    assert app._play_id is None and app._scan_id is None


def test_scope_bad_file_pause_empty_scan_and_interval_validation(app, collection):
    (collection / "file20.dat").write_text('VARIABLES="X" "Y"\nZONE I=2,J=2,F=POINT\n0', encoding="utf-8")
    app.scan_folder(collection)
    finish_scan(app)
    app.scope.set("选中文件")
    app.files_tree.selection_set("file2.dat", "file20.dat")
    app.root.update()
    app.interval.set("nan")
    app.play()
    assert not app._playing and "间隔" in app.status.get()
    app.interval.set("0.005")
    app.play()
    deadline = time.monotonic() + 5
    while app._playing and time.monotonic() < deadline:
        app.root.update()
    assert not app._playing
    assert app.sequence.current == "file2.dat"
    assert "file20.dat" in app.status.get() and "已暂停" in app.status.get()
    assert next(item for item in app.sequence.files if item.relative_path == "file20.dat").message
    empty = collection / "empty"
    empty.mkdir()
    app.scan_folder(empty)
    finish_scan(app)
    assert app.sequence.files == []
    assert str(app.play_button["state"]) == "disabled"


def test_missing_mapping_pause_freeze_limits_and_cancel_scan(app, collection):
    app.scan_folder(collection)
    finish_scan(app)
    app.load_item(app.sequence.ordered()[0])
    assert str(app.freeze_button["state"]) == "normal"
    app.freeze_button.invoke()
    fixed = app.result.info["clim"]
    assert app.load_item(app.sequence.ordered()[1])
    assert app.result.info["clim"] == fixed
    (collection / "file10.dat").write_text('VARIABLES="X" "Y" "P"\nZONE I=2,J=2,F=POINT\n0 0 1\n1 0 1\n0 1 1\n1 1 1', encoding="utf-8")
    previous = app.dataset
    assert not app.load_item(app.sequence.ordered()[1])
    assert app.dataset is previous
    assert "缺少已选变量" in app.status.get()
    app.scan_folder(collection)
    app.close()
    assert app._scan_id is None
    assert app._scan_iterator is None


@pytest.mark.parametrize("selection", ["zone", "k_slice"])
def test_unavailable_zone_or_k_is_not_silently_replaced(app, collection, selection):
    path = collection / "file2.dat"
    text = path.read_text(encoding="utf-8")
    rows = "\n".join(text.splitlines()[2:]) + "\n"
    text = (text + "ZONE I=2,J=2,F=POINT\n" + rows if selection == "zone" else
            text.replace("I=2,J=2", "I=2,J=2,K=2") + rows)
    path.write_text(text, encoding="utf-8")
    app.scan_folder(collection)
    finish_scan(app)
    app.load_item(app.sequence.ordered()[0])
    app.values[selection].set("2: Zone 2" if selection == "zone" else "2")
    app.redraw()
    previous = app.dataset
    assert not app.load_item(app.sequence.ordered()[1])
    assert app.dataset is previous
    assert "Zone / K" in app.status.get()


def test_rescan_replaces_cancelled_scan_without_late_updates(app, collection):
    empty = collection / "empty"
    empty.mkdir()
    app.scan_folder(collection)
    app.scan_folder(empty)
    finish_scan(app)
    assert app.folder == empty
    assert app.sequence.files == []
    assert app._scan_iterator is None


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
