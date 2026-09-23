# Tecplot DAT 查看器 · Python

MATLAB 版本的独立 Python 移植包：读取 Tecplot ASCII/PIV DAT，提供桌面界面、七种基础绘图、命令行导出和 Python API。运行时不需要 MATLAB 或 Tecplot。

## 安装与运行

需要 **Python 3.10+**，运行依赖 NumPy、Matplotlib。桌面界面使用 Python 标准库 `tkinter`；Windows/macOS 官方 Python 安装通常附带 Tcl/Tk，Linux 可由系统包管理器安装 `python3-tk`。命令行导出不需要桌面显示或 Tk。

在 PowerShell 中进入本目录，建立独立环境：

```powershell
cd D:\myDocuments\BUAA\tecplot\python
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m tecplot_viewer gui --demo
```

本次开发已在 `python/.venv/` 配好本机环境，可以直接运行最后一行。常规使用只需 `pip install .`，无需安装 `[dev]` 测试依赖。

安装后提供 `tecplot-viewer` 命令，与 `python -m tecplot_viewer` 等价。以下命令需在相应 Python 环境中执行；不想激活环境时，将 `python` 换成 `.\.venv\Scripts\python.exe`。Linux/macOS 的环境路径为 `.venv/bin/python`。

```powershell
# 桌面前端 / 指定文件 / 合成演示
python -m tecplot_viewer gui
python -m tecplot_viewer gui "D:\data\PivVector_001_002.dat"
python -m tecplot_viewer gui --demo

# 生成同截图规格的合成 DAT，不会默认覆盖已有文件
python -m tecplot_viewer demo synthetic_piv.dat

# 校验文件，查看变量与数据区
python -m tecplot_viewer inspect synthetic_piv.dat
python -m tecplot_viewer inspect synthetic_piv.dat --json

# 云图 + 箭头，自定义 colorbar 下限和上限
python -m tecplot_viewer plot synthetic_piv.dat -o velocity.png --variable Velocity --mode overlay --clim 0 0.06

# 涡量等值线 / 流线
python -m tecplot_viewer plot synthetic_piv.dat -o vorticity.pdf --variable Vorticity --mode contour
python -m tecplot_viewer plot synthetic_piv.dat -o streamlines.png --mode streamlines
```

导出支持 PNG、PDF、JPEG、SVG、TIFF，默认 300 DPI。输出目录需已存在，已有同名图片会被覆盖。输入错误返回非零退出码并说明原因。`--help` 可查看全部参数。

## 界面使用

左侧选择文件、Zone、变量、绘图模式、K 层、配色、箭头疏密/缩放以及 X/Y/U/V 列。右侧提供缩放、平移和三维曲面旋转工具栏。

取消勾选“自动色标范围”，输入独立的“色标下限”“色标上限”，按回车或离开输入框即可更新。要求上下限为有限数值且下限小于上限，支持负数、小数、科学计数法。手动范围在切换变量和绘图模式时保留，重新勾选即可恢复自动；重新载入文件恢复自动范围。纯箭头与网格图没有色标，控件暂时禁用。导出使用当前有效绘图设置。

Flag 默认不筛选；只有确定标记含义时才填 `1` 或 `1,2`。筛选不会修改原始数据。Y 轴默认向上，可改为图像坐标方向。输入无效时显示错误并暂停导出，避免把旧图误当作新设置的结果。

## Python API

```python
from tecplot_viewer import read_tecplot_dat, tecplot_grid, tecplot_plot, tecplot_cli

d = read_tecplot_dat("synthetic_piv.dat")
print(d.variables)                 # 保留括号、单位和变量名
print(d.zones[0].data.shape)       # (12087, 9)
u = tecplot_grid(d, "U", zone=1)   # (79, 153, 1)
u_xy = u[:, :, 0]

result = tecplot_plot(d, variable="Velocity", mode="overlay", clim=(0, 0.06))
result.save("velocity.png")
fig, ax, info = result             # 也可以访问 result.figure / .axes / .info

# 批处理导出后释放图形，返回绘图数组信息
info = tecplot_cli(d, "vorticity.png", variable="Vorticity", mode="contour")
```

API 不自动弹出图窗，适用于服务器和脚本。在 Notebook 中显示 `result.figure`，或向 `tecplot_plot` 传 `axes=ax` 嵌入已有图。曲面需要 `projection="3d"` 的 axes。桌面窗口使用：

```python
from tecplot_viewer import tecplot_viewer, demo_dataset
app = tecplot_viewer(demo_dataset())
app.run()
```

**索引约定**：函数参数 `zone`、`k_slice`、数值形式的 `variable` 都从 **1** 开始，与 MATLAB 和 CLI 一致；`dataset.zones[0]` 和 NumPy 数组仍用 Python 的 **0** 起始下标。`tecplot_variable(...)` 返回零起始列索引，`tecplot_grid(...)` 固定返回三维 `(J,I,K)`，即使 K=1 也不压缩维度。

## MATLAB 脚本逐项对应

| MATLAB 文件 | Python 文件 / 入口 | 职责 |
|---|---|---|
| `read_tecplot_dat.m` | `src/tecplot_viewer/read_tecplot_dat.py` | 严格解析和校验 DAT |
| `tecplot_variable.m` | `src/tecplot_viewer/tecplot_variable.py` | 名称、单位后缀、列号匹配 |
| `tecplot_grid.m` | `src/tecplot_viewer/tecplot_grid.py` | I 最快排列恢复为 J/I/K |
| `tecplot_plot.m` | `src/tecplot_viewer/tecplot_plot.py` | 七种模式、筛选、色标、输出 |
| `tecplot_viewer.m` | `src/tecplot_viewer/gui.py`，公开函数 `tecplot_viewer()` | Tk + Matplotlib 桌面界面 |
| `tecplot_cli.m` | `src/tecplot_viewer/tecplot_cli.py` | 无窗口导出函数 |
| `make_demo_dat.m` | `src/tecplot_viewer/make_demo_dat.py` | 同一公式和规格的合成数据 |
| `run_demo.m` | `run_demo.py` / `gui --demo` | 一键演示 |
| `build_examples.m` | `build_examples.py` | 生成示例图片/PDF |
| `tests/TestTecplot.m`、`run_tests.m` | `tests/`、`python -m pytest` | Python 回归与界面测试 |

参数采用 Python 小写下划线风格：

| MATLAB 参数 | Python 参数 | CLI |
|---|---|---|
| `Mode`, `Variable` | `mode`, `variable` | `--mode`, `--variable` |
| `Zone`, `KSlice` | `zone`, `k_slice` | `--zone`, `--k-slice` |
| `Levels`, `Stride` | `levels`, `stride` | `--levels`, `--stride` |
| `VectorScale` | `vector_scale` | `--vector-scale` |
| `CLim` | `clim=(lower,upper)` / `None` | `--clim LOWER UPPER` / 省略 |
| `Colormap` | `colormap` | `--colormap` |
| `ReverseY` | `reverse_y` | `--reverse-y` |
| `ValidFlagValues` | `valid_flag_values` | `--valid-flags 1 2` |
| `X/Y/U/V/WVariable` | `x/y/u/v/w_variable` | `--x-variable` 等 |
| `FlagVariable` | `flag_variable` | `--flag-variable` |
| `Axes`, `Output` | `axes`, `output` | `-o / --output` |

`mode` 支持 `heatmap`、`contour`、`quiver`、`overlay`、`streamlines`、`surface`、`mesh`。`variable="speed"` 计算速度模，W 缺失按 0 处理；指定 `"Velocity"` 则读取文件已有速度列。只有 W 参与速度模，二维箭头/流线只使用 U/V。

## 兼容范围与绘图差异

- 与 MATLAB 版相同，支持 ASCII 有序网格、节点数据、显式 I/J/K、POINT/BLOCK、多 Zone、跨行表头、注释、UTF-8 BOM、E/D 指数、时间标记；严格检查数值个数和格式。
- 不支持二进制 PLT/SZPLT、有限元网格、VARLOCATION、变量共享、被动变量、AUXDATA/几何文本记录或重复值简写。不是完整 Tecplot 引擎。
- XY 绘图要求 I/J 至少为 2，K>1 可选 K 层。曲面高度为标量值，网格为 XY 投影；没有体渲染、任意空间切片或三维流线。
- 数据值、坐标顺序和掩蔽语义与 MATLAB 对齐；渲染器不同，图像不保证逐像素一致。默认配色为 Matplotlib `viridis`，不冒充 MATLAB 的 `parula`。
- 正的 `vector_scale` 控制最长箭头相对采样网格间距的长度；0 使用原始分量长度。箭头是视觉缩放，不表示已换算单位的粒子位移。
- 手动色标范围同时控制归一化和填色等值线级别；超出范围的值使用端点颜色，原始标量不截断。
- 流线支持升序/降序的直角网格。Matplotlib 流线要求等间距，因此非均匀网格只对流线计算输入进行线性重采样，原始数据和背景云图不变；NaN/Flag 缺口不填补。`result.info["stream_resampled"]` 标明是否重采样。[Matplotlib 流线文档](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.streamplot.html)
- 坐标与速度单位保留；X/Y 应同单位，U/V 应同单位。NaN/Inf 场值作为缺失数据，非有限坐标拒绝绘图。读取整文件，超大数据可能需要专用流式实现。

## 测试、示例和打包

```powershell
python -m pytest -q                        # 包括真实 Tk 界面测试
python -m pytest -q --require-gui          # 发布验证：Tk 不可用时失败，禁止跳过
python -m pytest -q -m "not gui"           # 没有桌面的主机
python build_examples.py                  # output/ 下生成预览
python -m build                           # dist/ 下生成 wheel 和源码包
```

GUI 测试需要可用的 Tcl/Tk 和桌面，环境不可用时会报告跳过，不能将跳过视为已验证。`src/tecplot_viewer/data/synthetic_piv.dat` 是 MATLAB 版本原有的合成样本，随 wheel 一起分发；不是截图中的原始实验数据。Python 代码不依赖兄弟 `matlab/` 目录。

`requirements-tested.txt` 记录本机验证时的精确依赖版本（Python 3.12/Windows）；跨平台安装优先使用 `pyproject.toml` 中的版本范围。

所有代码、依赖声明、测试和文档均在 `python/`。虚拟环境、缓存、生成图片和构建产物由本目录 `.gitignore` 排除。打包采用标准 `pyproject.toml` 和 console script 入口。[Python 包装指南](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)

可选的 MATLAB 数值交叉验证（仅开发验证需要 MATLAB）：在仓库根目录的 MATLAB 中执行 `addpath('python/validation'); export_matlab_reference`，再在 `python/` 中运行 `python validation/compare_matlab_reference.py`。它比较全部 12,087×9 数据、七个网格变量以及 Flag 过滤后的速度模/U/V，容差为 `rtol=1e-12, atol=1e-14`，缺失值位置也必须一致。

2026-09-23 本机 Windows/Python 3.12 验证：**65 项测试通过，0 跳过**；原始矩阵与七个网格变量和 MATLAB 结果完全一致，计算速度模最大差异约 `5.6e-17`。wheel 已独立安装并验证内置样本、CLI 和桌面界面。详细环境与验证边界见 [VALIDATION.md](VALIDATION.md)。
