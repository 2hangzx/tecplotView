"""Tk desktop front end corresponding to tecplot_viewer.m.

The module is named gui to keep the lazy public tecplot_viewer() function
callable after the GUI has been imported, including repeated notebook use.
"""
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np

from .make_demo_dat import demo_dataset
from .models import Dataset, TecplotError
from .read_tecplot_dat import read_tecplot_dat
from .tecplot_plot import tecplot_plot
from .tecplot_variable import tecplot_variable

MODE_LABELS = {"云图 + 箭头": "overlay", "彩色云图": "heatmap", "填色等值线": "contour",
               "速度箭头": "quiver", "流线 + 云图": "streamlines", "标量曲面": "surface", "网格": "mesh"}
SPEED_LABEL = "速度模（由 U,V,W 计算）"
UNASSIGNED = "请选择"


class TecplotViewer:
    """Native desktop app. Use run() to enter the window event loop.

    With visible=False the real Tk widgets are constructed offscreen, useful
    for integration tests. Rendering/exports use the same Python API as CLI.
    """

    def __init__(self, source=None, *, root=None, visible=True):
        try:
            self.root = root if root is not None else tk.Tk()
        except tk.TclError as exc:
            raise TecplotError("GUI", "A desktop display and working Python Tcl/Tk installation are required; CLI plotting works without Tk.") from exc
        if not visible:
            self.root.withdraw()
        self.root.title("Tecplot DAT 查看器 · Python")
        self.root.geometry("1280x850")
        self.root.minsize(850, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.dataset = None
        self.result = None
        self._busy = False
        self.values, self.controls = {}, {}
        self.status = tk.StringVar(self.root, value="打开 DAT 文件，或载入合成示例。")
        self.figure = Figure(figsize=(10, 7), layout="constrained", facecolor="white")
        self._build_ui()
        if source is not None:
            try:
                self.load(source)
            except Exception:
                self.close()
                raise

    def _build_ui(self):
        status_label = ttk.Label(self.root, textvariable=self.status, anchor="w", padding=8)
        status_label.pack(side="bottom", fill="x")
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True)
        sidebar = ttk.Frame(body, width=310)
        sidebar.pack(side="left", fill="y")
        scroll = tk.Canvas(sidebar, width=295, highlightthickness=0)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=scroll.yview)
        scrollbar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        scroll.configure(yscrollcommand=scrollbar.set)
        self.panel = ttk.Frame(scroll, padding=10)
        panel_id = scroll.create_window((0, 0), window=self.panel, anchor="nw")
        self.panel.bind("<Configure>", lambda event: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(panel_id, width=event.width))
        self.panel.columnconfigure(1, weight=1)
        self._row = 0
        for text, command in (("打开 DAT 文件", self.open_file), ("载入合成示例", self.load_demo)):
            ttk.Button(self.panel, text=text, command=command).grid(row=self._row, column=0, columnspan=2, sticky="ew", pady=4)
            self._row += 1
        self._combo("zone", "数据区 Zone", [UNASSIGNED])
        self._combo("variable", "显示变量", [SPEED_LABEL])
        self._combo("mode", "绘图类型", list(MODE_LABELS))
        for key, label, default in (("k_slice", "K 层", "1"), ("stride", "箭头/流线间隔", "5"),
                                    ("levels", "等值线级数", "24"), ("vector_scale", "箭头缩放", "1.2")):
            self._entry(key, label, default)
        self._combo("colormap", "配色", ["viridis", "turbo", "jet", "coolwarm", "gray", "hot", "cool"])
        self._check("auto_clim", "自动色标范围", True)
        self._entry("clim_min", "色标下限", "0")
        self._entry("clim_max", "色标上限", "1")
        self._entry("flags", "保留 Flag 值", "")
        for key, label in (("x_variable", "X 坐标列"), ("y_variable", "Y 坐标列"),
                           ("u_variable", "U 速度列"), ("v_variable", "V 速度列")):
            self._combo(key, label, [UNASSIGNED])
        self._check("reverse_y", "Y 轴向下增大（图像坐标）", False)
        ttk.Button(self.panel, text="更新绘图", command=self.redraw).grid(row=self._row, column=0, columnspan=2, sticky="ew", pady=5)
        self._row += 1
        self.export_button = ttk.Button(self.panel, text="导出图片 / PDF", command=self.save_dialog, state="disabled")
        self.export_button.grid(row=self._row, column=0, columnspan=2, sticky="ew", pady=5)
        self._row += 1
        ttk.Label(self.panel, text="Flag 留空：保留全部数据。\n自定义范围：下限必须小于上限。\n标量曲面的高度是变量值。", wraplength=265, padding=(0, 8)).grid(row=self._row, column=0, columnspan=2, sticky="w")
        plot_panel = ttk.Frame(body, padding=8)
        plot_panel.pack(side="right", fill="both", expand=True)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_panel)
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_panel, pack_toolbar=False)
        self.toolbar.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        self._update_limit_controls()

    def _combo(self, key, label, items):
        ttk.Label(self.panel, text=label).grid(row=self._row, column=0, sticky="w", padx=(0, 7), pady=4)
        variable = tk.StringVar(self.root, value=items[0])
        widget = ttk.Combobox(self.panel, textvariable=variable, values=items, state="readonly", width=20)
        widget.grid(row=self._row, column=1, sticky="ew", pady=4)
        widget.bind("<<ComboboxSelected>>", self.redraw)
        self.values[key], self.controls[key] = variable, widget
        self._row += 1

    def _entry(self, key, label, value):
        ttk.Label(self.panel, text=label).grid(row=self._row, column=0, sticky="w", padx=(0, 7), pady=4)
        variable = tk.StringVar(self.root, value=value)
        widget = ttk.Entry(self.panel, textvariable=variable, width=20)
        widget.grid(row=self._row, column=1, sticky="ew", pady=4)
        widget.bind("<Return>", self.redraw)
        widget.bind("<FocusOut>", self.redraw)
        self.values[key], self.controls[key] = variable, widget
        self._row += 1

    def _check(self, key, label, value):
        variable = tk.BooleanVar(self.root, value=value)
        widget = ttk.Checkbutton(self.panel, text=label, variable=variable, command=self.redraw)
        widget.grid(row=self._row, column=0, columnspan=2, sticky="w", pady=6)
        self.values[key], self.controls[key] = variable, widget
        self._row += 1

    @staticmethod
    def _column(value):
        if value == SPEED_LABEL:
            return "speed"
        if value == UNASSIGNED:
            raise TecplotError("Variable", "请先选择所需的坐标 / 速度列。")
        return int(value.split(":", 1)[0])

    def load(self, source):
        """Load a path or Dataset; reset color limits to automatic."""
        candidate = read_tecplot_dat(source) if isinstance(source, (str, Path)) else source
        if not isinstance(candidate, Dataset):
            raise TypeError("Expected DAT path or Dataset")
        self.dataset = candidate
        self._busy = True
        try:
            names = [f"{n}: {name}" for n, name in enumerate(candidate.variables, 1)]
            zones = [f"{n}: {z.name}" for n, z in enumerate(candidate.zones, 1)]
            self.controls["zone"].configure(values=zones)
            self.values["zone"].set(zones[0])
            self.controls["variable"].configure(values=[SPEED_LABEL, *names])
            speed = tecplot_variable(candidate.variables, "Velocity", False)
            self.values["variable"].set(SPEED_LABEL if speed is None else names[speed])
            found = {}
            for key, name in (("x_variable", "X"), ("y_variable", "Y"), ("u_variable", "U"), ("v_variable", "V")):
                index = tecplot_variable(candidate.variables, name, False)
                found[name] = index
                self.controls[key].configure(values=[UNASSIGNED, *names])
                self.values[key].set(UNASSIGNED if index is None else names[index])
            if found["U"] is None or found["V"] is None:
                self.values["mode"].set("彩色云图")
                if speed is None:
                    scalar_index = next((n for n in range(len(names)) if n not in (found["X"], found["Y"])), 0)
                    self.values["variable"].set(names[scalar_index])
            self.values["auto_clim"].set(True)
            self.values["flags"].set("")
            self.values["k_slice"].set("1")
        finally:
            self._busy = False
        if found["X"] is None or found["Y"] is None:
            self.figure.clear()
            self.result = None
            self.canvas.draw_idle()
            self.export_button.configure(state="disabled")
            self.status.set("数据已读取，请从下拉菜单选择 X、Y 坐标列。")
            self._update_limit_controls()
        else:
            self.render()

    def _update_limit_controls(self):
        enabled = self.dataset is not None and MODE_LABELS[self.values["mode"].get()] not in {"quiver", "mesh"}
        self.controls["auto_clim"].configure(state="normal" if enabled else "disabled")
        for key in ("clim_min", "clim_max"):
            self.controls[key].configure(state="normal" if enabled and not self.values["auto_clim"].get() else "disabled")

    def render(self):
        """Render current controls; errors leave the prior valid figure intact."""
        if self.dataset is None:
            raise TecplotError("NoData", "请先打开 DAT 文件。")
        self.export_button.configure(state="disabled")
        self._update_limit_controls()
        values = {key: var.get() for key, var in self.values.items()}
        mode = MODE_LABELS[values["mode"]]
        has_colorbar = mode not in {"quiver", "mesh"}
        zone = int(values["zone"].split(":", 1)[0])
        k_slice = min(int(values["k_slice"]), self.dataset.zones[zone - 1].k)
        self.values["k_slice"].set(str(k_slice))
        clim = None
        if has_colorbar and not values["auto_clim"]:
            clim = (float(values["clim_min"]), float(values["clim_max"]))
            if not np.all(np.isfinite(clim)) or clim[0] >= clim[1]:
                raise TecplotError("ColorLimits", "色标上下限必须是有限数值，且下限必须小于上限。")
        flags = [float(token) for token in re.split(r"[,;\s]+", values["flags"].strip())] if values["flags"].strip() else None
        selected = self._column(values["variable"])
        mappings = {key: self._column(values[key]) for key in ("x_variable", "y_variable")}
        needs_uv = mode in {"quiver", "overlay", "streamlines"} or (has_colorbar and selected == "speed")
        if needs_uv:
            mappings.update({key: self._column(values[key]) for key in ("u_variable", "v_variable")})
        result = tecplot_plot(self.dataset, figure=self.figure, mode=mode, variable=selected, zone=zone,
                              k_slice=k_slice, stride=int(values["stride"]), levels=int(values["levels"]),
                              vector_scale=float(values["vector_scale"]), colormap=values["colormap"],
                              clim=clim, valid_flag_values=flags, reverse_y=values["reverse_y"], **mappings)
        self.result = result
        if has_colorbar and values["auto_clim"]:
            self.values["clim_min"].set(format(result.info["clim"][0], ".12g"))
            self.values["clim_max"].set(format(result.info["clim"][1], ".12g"))
        self.toolbar.update()
        self.canvas.draw_idle()
        self.export_button.configure(state="normal")
        z = self.dataset.zones[zone - 1]
        self.status.set(f"{z.name} | {z.i} × {z.j} × {z.k} | {len(z.data)} 个点 | {z.packing} | K={k_slice}")
        return result

    def redraw(self, event=None):
        if self._busy:
            return
        self._update_limit_controls()
        if self.dataset is None:
            return
        try:
            self._busy = True
            self.render()
        except (ValueError, OSError) as exc:
            self.status.set(f"错误：{exc}")
            self.export_button.configure(state="disabled")
        finally:
            self._busy = False

    def open_file(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Tecplot ASCII", "*.dat *.tec *.txt"), ("全部文件", "*.*")])
        if path:
            try:
                self.load(path)
            except (ValueError, OSError) as exc:
                self.status.set(f"错误：{exc}")
                self.export_button.configure(state="disabled")
                messagebox.showerror("读取失败", str(exc), parent=self.root)

    def load_demo(self):
        self.load(demo_dataset())

    def export(self, filename, *, dpi=300):
        if self.result is None or str(self.export_button["state"]) == "disabled":
            raise TecplotError("NoData", "请先完成一次有效绘图。")
        return self.result.save(filename, dpi=dpi)

    def save_dialog(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".png", initialfile="tecplot.png",
                                          filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("JPEG", "*.jpg"), ("SVG", "*.svg")])
        if path:
            try:
                self.export(path)
                self.status.set(f"已导出：{path}")
            except (ValueError, OSError) as exc:
                messagebox.showerror("导出失败", str(exc), parent=self.root)

    def run(self):
        self.root.mainloop()

    def close(self):
        # Drain a scheduled draw before destroying its canvas/Tk interpreter.
        pending = getattr(self.canvas, "_idle_draw_id", None)
        if pending:
            # The canvas owns the registered Tcl callback, so it must also
            # unregister it. Cancelling through root leaves a stale command
            # in the canvas and raises TclError during widget destruction.
            self.canvas.get_tk_widget().after_cancel(pending)
            self.canvas._idle_draw_id = None
        self.figure.clear()
        self.root.destroy()
