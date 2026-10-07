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
from .scan_dat import iter_scan_dat
from .sequence import FileSequence

MODE_LABELS = {"云图 + 箭头": "overlay", "彩色云图": "heatmap", "填色等值线": "contour",
               "速度箭头": "quiver", "流线 + 云图": "streamlines", "标量曲面": "surface", "网格": "mesh"}
SPEED_LABEL = "速度模（由 U,V,W 计算）"
UNASSIGNED = "请选择"


class TecplotViewer:
    """Native desktop app. Use run() to enter the window event loop.

    With visible=False the real Tk widgets are constructed offscreen, useful
    for integration tests. Rendering/exports use the same Python API as CLI.
    """

    def __init__(self, source=None, *, root=None, visible=True, folder=None, recursive=False):
        if source is not None and folder is not None:
            raise ValueError("Choose a file/dataset or a folder.")
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
        self._closed = False
        self.sequence = FileSequence()
        self.folder = None
        self._playing = False
        self._play_id = self._scan_id = None
        self._scan_iterator = None
        self._scan_generation = 0
        self._list_updating = False
        self.values, self.controls = {}, {}
        self.status = tk.StringVar(self.root, value="打开 DAT 文件，或载入合成示例。")
        self.figure = Figure(figsize=(10, 7), layout="constrained", facecolor="white")
        self._build_ui()
        self.recursive.set(recursive)
        if source is not None:
            try:
                self.load(source)
            except Exception:
                self.close()
                raise
        if folder is not None:
            try:
                self.scan_folder(folder)
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
        self._build_browser()
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
        self.freeze_button = ttk.Button(self.panel, text="固定当前色标范围", command=self.freeze_limits, state="disabled")
        self.freeze_button.grid(row=self._row, column=0, columnspan=2, sticky="ew", pady=4)
        self._row += 1
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

    def _build_browser(self):
        box = ttk.LabelFrame(self.panel, text="文件夹浏览与播放", padding=5)
        box.grid(row=self._row, column=0, columnspan=2, sticky="ew", pady=5)
        self._row += 1
        box.columnconfigure(0, weight=1)
        self.folder_label = ttk.Label(box, text="未选择文件夹", wraplength=250)
        self.folder_label.grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Button(box, text="选择文件夹", command=self.choose_folder).grid(row=1, column=0, sticky="ew")
        self.refresh_button = ttk.Button(box, text="重新扫描", command=self.refresh_folder)
        self.refresh_button.grid(row=1, column=1, sticky="ew")
        self.recursive = tk.BooleanVar(self.root, value=False)
        ttk.Checkbutton(box, text="包含子文件夹", variable=self.recursive).grid(row=2, column=0, columnspan=2, sticky="w")
        self.files_tree = ttk.Treeview(box, columns=("status",), show="tree headings", height=5, selectmode="extended")
        self.files_tree.heading("#0", text="文件（相对路径）")
        self.files_tree.heading("status", text="验证状态")
        self.files_tree.column("#0", width=160, minwidth=80)
        self.files_tree.column("status", width=85, minwidth=60, stretch=False)
        self.files_tree.grid(row=3, column=0, columnspan=2, sticky="ew")
        bar = ttk.Scrollbar(box, orient="vertical", command=self.files_tree.yview)
        bar.grid(row=3, column=2, sticky="ns")
        self.files_tree.configure(yscrollcommand=bar.set)
        self.files_tree.bind("<<TreeviewSelect>>", self._file_selected)
        self.order = tk.StringVar(self.root, value="正序")
        self.scope = tk.StringVar(self.root, value="全部文件")
        for row, var, values in ((4, self.order, ("正序", "倒序")), (5, self.scope, ("全部文件", "选中文件"))):
            widget = ttk.Combobox(box, textvariable=var, values=values, state="readonly", width=16)
            widget.grid(row=row, column=0, columnspan=2, sticky="ew", pady=2)
            widget.bind("<<ComboboxSelected>>", self._browser_option_changed)
        ttk.Button(box, text="上一文件", command=lambda: self.step_file(-1)).grid(row=6, column=0, sticky="ew")
        ttk.Button(box, text="下一文件", command=lambda: self.step_file(1)).grid(row=6, column=1, sticky="ew")
        self.play_button = ttk.Button(box, text="播放", command=self.toggle_play, state="disabled")
        self.play_button.grid(row=7, column=0, sticky="ew")
        ttk.Button(box, text="暂停", command=self.pause).grid(row=7, column=1, sticky="ew")
        ttk.Label(box, text="间隔（秒）").grid(row=8, column=0, sticky="w")
        self.interval = tk.StringVar(self.root, value="0.5")
        entry = ttk.Entry(box, textvariable=self.interval, width=8)
        entry.grid(row=8, column=1, sticky="ew")
        entry.bind("<Return>", self._browser_option_changed)
        entry.bind("<FocusOut>", self._browser_option_changed)
        self.loop = tk.BooleanVar(self.root, value=False)
        ttk.Checkbutton(box, text="循环播放", variable=self.loop, command=self._browser_option_changed).grid(row=9, column=0, columnspan=2, sticky="w")
        ttk.Label(box, text="Ctrl / Shift 多选；播放顺序不代表物理时间。", wraplength=250).grid(row=10, column=0, columnspan=2, sticky="w")

    def _browser_options(self):
        selected = set(self.files_tree.selection()) if self.scope.get() == "选中文件" else None
        return dict(reverse=self.order.get() == "倒序", selected=selected)

    def _browser_option_changed(self, event=None):
        self.pause()
        for n, item in enumerate(self.sequence.ordered(reverse=self.order.get() == "倒序")):
            self.files_tree.move(item.relative_path, "", n)

    def choose_folder(self):
        path = filedialog.askdirectory(parent=self.root)
        if path:
            self.scan_folder(path)

    def refresh_folder(self):
        if self.folder is not None:
            self.scan_folder(self.folder)

    def _cancel_scan(self):
        self._scan_generation += 1
        if self._scan_id is not None:
            self.root.after_cancel(self._scan_id)
            self._scan_id = None
        if self._scan_iterator is not None:
            self._scan_iterator.close()
            self._scan_iterator = None

    def scan_folder(self, folder):
        """Incrementally discover files; never automatically load or play them."""
        self.pause()
        self._cancel_scan()
        path = Path(folder).resolve(strict=True)
        if not path.is_dir():
            raise NotADirectoryError(str(path))
        self.folder_label.configure(text=f"正在扫描：{path}")
        self.play_button.configure(state="disabled")
        generation = self._scan_generation
        records, warnings = [], []
        iterator = iter_scan_dat(path, recursive=self.recursive.get(), warnings=warnings)
        self._scan_iterator = iterator
        self.status.set("正在扫描文件夹…")

        def batch():
            self._scan_id = None
            if self._closed or generation != self._scan_generation:
                return
            try:
                for _ in range(20):
                    records.append(next(iterator))
                self.status.set(f"正在扫描：发现 {len(records)} 个 DAT 文件…")
                self._scan_id = self.root.after(1, batch)
            except StopIteration:
                self._scan_iterator = None
                self.folder = path
                self.folder_label.configure(text=str(path))
                self.sequence = FileSequence(records)
                self._list_updating = True
                try:
                    self.files_tree.delete(*self.files_tree.get_children())
                    for item in self.sequence.ordered(reverse=self.order.get() == "倒序"):
                        self.files_tree.insert("", "end", iid=item.relative_path, text=item.relative_path, values=(item.status,))
                finally:
                    self._list_updating = False
                self.play_button.configure(state="normal" if records else "disabled")
                self.status.set(f"扫描完成：{len(records)} 个 DAT 文件。请选择文件绘图。" +
                                (f" {len(warnings)} 个目录无法扫描：{warnings[0]}" if warnings else ""))
            except OSError as exc:
                iterator.close()
                self._scan_iterator = None
                self.folder_label.configure(text=str(self.folder) if self.folder is not None else "未选择文件夹")
                self.play_button.configure(state="normal" if self.sequence.files else "disabled")
                self.status.set(f"扫描失败：{exc}")

        self._scan_id = self.root.after(0, batch)

    def _file_selected(self, event=None):
        if self._list_updating or self._scan_id is not None:
            return
        self.pause()
        name = self.files_tree.focus()
        item = next((item for item in self.sequence.files if item.relative_path == name), None)
        if item is not None and name != self.sequence.current:
            self.load_item(item)

    def load_item(self, item):
        try:
            self.load(item.path, preserve=self.sequence.current is not None, from_collection=True)
            self.canvas.draw()  # Complete this display before scheduling another file.
            self.sequence.current = item.relative_path
            item.status, item.message = "已读取", ""
            self.files_tree.focus(item.relative_path)
            self.files_tree.see(item.relative_path)
            ordered = self.sequence.ordered(**self._browser_options())
            position = next((n for n, record in enumerate(ordered, 1) if record is item), None)
            self.status.set(f"{item.relative_path} | 第 {position} / {len(ordered)} 个文件 | " + self.status.get()
                            if position is not None else f"{item.relative_path} | " + self.status.get())
            self.files_tree.item(item.relative_path, values=(item.status,))
            return True
        except (ValueError, OSError) as exc:
            self.pause()
            item.status, item.message = "读取失败", str(exc)
            self.files_tree.item(item.relative_path, values=(item.status,))
            self.export_button.configure(state="disabled")
            self.status.set(f"已暂停：{item.relative_path} | {exc}")
            return False

    def step_file(self, direction=1):
        self.pause()
        if self._scan_id is not None:
            return
        item = self.sequence.target(direction, **self._browser_options())
        if item is not None:
            self.load_item(item)

    def _interval_ms(self):
        value = float(self.interval.get())
        if not np.isfinite(value) or value <= 0:
            raise ValueError("播放间隔必须为大于 0 的有限秒数。")
        return max(1, int(round(value * 1000)))

    def play(self):
        if self._scan_id is not None or self._closed or self._playing:
            return
        try:
            self._interval_ms()
            items = self.sequence.ordered(**self._browser_options())
            if not items:
                raise ValueError("没有可播放的文件；请选择文件或更改播放范围。")
            if self.sequence.current not in {item.relative_path for item in items}:
                if not self.load_item(items[0]):
                    return
            self._playing = True
            self.play_button.configure(text="暂停")
            self._schedule_play()
        except (ValueError, OSError) as exc:
            self.pause()
            self.status.set(f"播放失败：{exc}")

    def toggle_play(self):
        self.pause() if self._playing else self.play()

    def _schedule_play(self):
        if self._playing:
            try:
                self._play_id = self.root.after(self._interval_ms(), self._play_tick)
            except ValueError as exc:
                self.pause()
                self.status.set(f"已暂停：{exc}")

    def _play_tick(self):
        self._play_id = None
        if not self._playing or self._closed:
            return
        item = self.sequence.target(**self._browser_options(), loop=self.loop.get())
        if item is None:
            self.pause()
            self.status.set(self.status.get() + " | 播放结束")
        elif self.load_item(item):
            self._schedule_play()

    def pause(self):
        self._playing = False
        if self._play_id is not None:
            self.root.after_cancel(self._play_id)
            self._play_id = None
        self.play_button.configure(text="播放")

    def freeze_limits(self):
        if self.result is not None and self.result.info["clim"] is not None:
            self.values["clim_min"].set(format(self.result.info["clim"][0], ".12g"))
            self.values["clim_max"].set(format(self.result.info["clim"][1], ".12g"))
            self.values["auto_clim"].set(False)
            self.redraw()

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

    def load(self, source, *, preserve=False, from_collection=False):
        """Load a path or Dataset; reset color limits to automatic."""
        if not from_collection:
            self.pause()
            self.sequence.current = None
        old_values = {key: value.get() for key, value in self.values.items()}
        candidate = read_tecplot_dat(source) if isinstance(source, (str, Path)) else source
        if not isinstance(candidate, Dataset):
            raise TypeError("Expected DAT path or Dataset")
        restored = {}
        if preserve and self.dataset is not None:
            for key in ("variable", "x_variable", "y_variable", "u_variable", "v_variable"):
                value = old_values[key]
                if value in (SPEED_LABEL, UNASSIGNED):
                    restored[key] = value
                    continue
                name = self.dataset.variables[self._column(value) - 1]
                if name not in candidate.variables:
                    raise TecplotError("Variable", f"新文件缺少已选变量 {name}；请单独打开文件重新配置。")
                restored[key] = f"{candidate.variables.index(name) + 1}: {name}"
            zone_index = int(old_values["zone"].split(":", 1)[0]) - 1
            if zone_index >= len(candidate.zones) or not 1 <= int(old_values["k_slice"]) <= candidate.zones[zone_index].k:
                raise TecplotError("Selection", "新文件没有所选 Zone / K 层；请单独打开文件重新配置。")
            restored["zone"] = f"{zone_index + 1}: {candidate.zones[zone_index].name}"
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
            if preserve:
                for key, value in old_values.items():
                    self.values[key].set(restored.get(key, value))
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
        self.freeze_button.configure(state="normal" if enabled and self.result is not None else "disabled")
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
        self._update_limit_controls()
        z = self.dataset.zones[zone - 1]
        self.status.set(f"{z.name} | {z.i} × {z.j} × {z.k} | {len(z.data)} 个点 | {z.packing} | K={k_slice}")
        return result

    def redraw(self, event=None):
        if self._busy:
            return
        self.pause()
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
        if self._closed:
            return
        self._closed = True
        self.pause()
        self._cancel_scan()
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
