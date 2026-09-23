# MATLAB Tecplot DAT 查看器

读取 Tecplot ASCII 有序网格文件，在 MATLAB 中查看 PIV 速度场、标量云图、等值线、流线及网格。提供独立读取函数、命令行绘图和交互界面，不需要 Tecplot 或额外 MATLAB 工具箱。

## 对截图的判断

**截图中的表头属于 Tecplot ASCII 有序网格格式。** `F=POINT` 是旧式逐点存储写法，对应现代写法 `DATAPACKING=POINT`。`.dat` 后缀本身不能判断格式，依据是截图中的 `TITLE`、`VARIABLES`、`ZONE`、`I/J/K` 和 `DT` 声明。参考 [Tecplot 格式规范](https://tecplot.azureedge.net/products/360/2024r1m1/360-data-format.html) 与仍使用 `F=POINT` 示例的 [Tecplot 官方手册](https://tecplot.azureedge.net/products/focus/2025r1/help/users_manual/animate.html)。

截图声明 `I=153, J=79, K=1`，共 **12,087 个网格点、9 个变量、108,783 个数值**。通常每行是一个点的九列数据，也允许数值换行。单层 `K=1` 且截图中 `Z/W=0`，适合二维 XY/PIV 显示；不能仅凭几行截图断言全部 Z/W 都为零。

| 列 | 变量 | 用途 |
|---|---|---|
| 1–3 | X(mm), Y(mm), Z(mm) | 坐标 |
| 4–6 | U(m/s), V(m/s), W(m/s) | 三个速度分量 |
| 7 | Velocity(m/s) | 文件已有的速度模 |
| 8 | Vorticity | 文件已有的涡量，单位/定义以导出软件为准 |
| 9 | Flag | 导出软件定义的标记，默认不据此过滤 |

本项目按截图规格开发。没有原始 DAT，无法验证原文件的数据完整性；附带数据是明确标注的**合成演示场，非实验数据**。

## 立即运行

在 MATLAB 中执行：

```matlab
cd('D:\myDocuments\BUAA\tecplot\matlab');
run_demo                         % 直接打开合成数据的交互界面
```

打开自己的文件：

```matlab
tecplot_viewer                   % 打开界面，点“打开 DAT 文件”
tecplot_viewer('D:\data\PivVector_001_002.dat')
```

环境：推荐 MATLAB R2021a 或更新版本；本机验证环境为 R2026a。使用基础 MATLAB 的 `uifigure`、`contourf`、`surf`、`quiver`、`stream2` 和 `exportgraphics`，无需 App Designer 工程、插件或工具箱。其他 MATLAB 版本未实机验证。

界面可以切换数据区、标量变量、绘图模式、K 层、配色、色标范围、箭头疏密与缩放，以及 X/Y/U/V 列。支持缩放、平移和 PNG/PDF/JPEG 导出。Y 轴默认向上；若原始数据采用图像坐标，可勾选“Y 轴向下增大”。

自定义 colorbar 上下限：取消勾选“自动色标范围”，分别输入“色标下限”和“色标上限”（如 `0` 和 `0.06`），按回车或离开输入框后立即更新。支持负数、小数和科学计数法，下限必须小于上限。切换变量、配色或有色标的绘图模式时保留手动范围；导出的图片使用同一范围。重新勾选“自动色标范围”可恢复自动，并在两个输入框显示当前范围。重新打开数据文件会恢复自动范围。纯箭头和网格图没有色标，相应控件暂时禁用。

## 命令行调用

```matlab
file = fullfile(pwd, 'examples', 'synthetic_piv.dat');

% 使用文件已有的 Velocity 列：云图叠加速度箭头
tecplot_plot(file, 'Variable', 'Velocity', 'Mode', 'overlay');

% 涡量云图；变量可用完整名称、去掉单位的名称或列号
tecplot_plot(file, 'Variable', 'Vorticity', 'Mode', 'contour', ...
    'Levels', 30, 'Output', 'vorticity.png');

% 由 U/V/W 重新计算速度模，显示二维流线
tecplot_plot(file, 'Variable', 'speed', 'Mode', 'streamlines');

% 自定义 colorbar 下限与上限；CLim=[] 恢复自动
tecplot_plot(file, 'Variable', 'Velocity', 'CLim', [0 0.06]);

% 仅当你确认 Flag=1 表示需要保留的数据时才使用该过滤
tecplot_plot(file, 'ValidFlagValues', 1, 'Stride', 6, 'CLim', [0 0.06]);

% 完成后自动关闭绘图窗口，适合批处理
tecplot_cli(file, 'velocity.png', 'Variable', 'Velocity', 'Mode', 'overlay');
```

Windows PowerShell 中调用（MATLAB 已在 PATH 时）：

```powershell
matlab -batch "cd('D:\myDocuments\BUAA\tecplot\matlab'); tecplot_cli('examples/synthetic_piv.dat','velocity.png','Mode','overlay','Variable','Velocity')"
```

批量处理一组 DAT，在同一色标下便于比较：

```matlab
inputDir = 'D:\data';
outputDir = fullfile(inputDir, 'images');
if ~isfolder(outputDir), mkdir(outputDir); end
files = dir(fullfile(inputDir, '*.dat'));
for n = 1:numel(files)
    [~, name] = fileparts(files(n).name);
    tecplot_cli(fullfile(files(n).folder, files(n).name), ...
        fullfile(outputDir, [name '.png']), ...
        'Variable', 'Velocity', 'Mode', 'overlay', 'CLim', [0 0.06]);
end
```

输出目录需要存在；导出至已有同名图片会覆盖该图片。批量脚本遇到错误即停止并显示原因。

## 读取数据继续分析

```matlab
D = read_tecplot_dat('examples/synthetic_piv.dat');
D.Variables                     % 保留括号、单位等原始变量名
D.Zones(1).Data                  % [12087 × 9]，原文件节点顺序
U = tecplot_grid(D, 'U', 1);      % [79 × 153]，U(j,i,k)
X = tecplot_grid(D, 'X', 1);
Y = tecplot_grid(D, 'Y', 1);
```

Tecplot 节点按 I 最快、J 次之、K 最后排列。`tecplot_grid` 先按 `[I,J,K]` 恢复，再转换为 MATLAB 绘图习惯的 `[J,I,K]`。第三个参数是 Zone 序号，均从 1 开始。

主要参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `Mode` | `overlay` | `heatmap`、`contour`、`quiver`、`overlay`、`streamlines`、`surface`、`mesh` |
| `Variable` | `speed` | `speed` 为计算速度模；可指定文件变量名或列号 |
| `Zone` / `KSlice` | `1` / `1` | 选择数据区和 XY 层 |
| `Stride` | `5` | 每隔几个网格点绘制箭头；也调节流线种子疏密 |
| `VectorScale` | `1.2` | MATLAB quiver 自动缩放系数；0 表示原始分量长度 |
| `Levels` | `24` | 填色等值线的级数 |
| `Colormap` | `parula` | 常用配色名或 N×3 的 RGB 矩阵 |
| `CLim` | `[]` | 自动范围，或 `[最小值 最大值]` |
| `ValidFlagValues` | `[]` | 全保留，或允许的 Flag 数值，例如 `[1 2]` |
| `ReverseY` | `false` | 是否使 Y 轴向下增大 |
| `X/Y/U/V/WVariable` | 相应字母 | 实际参数名如 `XVariable`；名称或列号 |
| `FlagVariable` | `Flag` | 可用数值列号指定其他标记列 |
| `Axes` | `[]` | 可传入现有 axes/uiaxes 进行嵌入式绘图 |
| `Output` | 空 | 文件名，例如 `plot.png` 或 `plot.pdf` |
| `Visible` | `on` | 新图窗的可见性；提供 Axes 时使用已有窗口 |

`[fig,ax,info] = tecplot_plot(...)` 返回图窗、坐标轴及实际绘图数组，便于后续修改。命令行调用默认计算速度模，GUI 在存在 `Velocity` 时优先选择文件已有速度模。W 列缺失时，计算速度模按 W=0 处理；存在 W 时参与模长计算，二维箭头/流线只使用 U/V。若文件恰有名为 `speed` 的列，用列号选择它，以区分计算模式。

## 支持范围与边界

- 支持 ASCII、有序网格、节点数据、显式 I/J/K 尺寸、POINT/BLOCK、多 Zone、跨行表头、空白/逗号分隔、注释、UTF-8 BOM、E/D 指数以及时间标记。
- 检查每个 Zone 的总数值数量和数字格式，不会在遇到错误文本时静默截断。读取时保留 NaN/Inf，绘图将非有限场值作为缺失数据；非有限 X/Y 坐标会报错。
- 绘图针对 I/J 都至少为 2 的 XY 平面。K>1 可选择 K 层；`surface` 的高度是标量值，`mesh` 是 XY 投影网格；不提供体渲染、等值面、任意空间切片或三维流线。
- 流线要求单调的直角网格，支持升序和降序，支持不均匀间距；曲线网格可用云图、箭头或网格显示。流线是方向可视化，不是带物理时间的粒子轨迹。
- 坐标和速度单位原样保留。截图坐标为 mm、速度为 m/s；默认箭头按图面自动缩放，箭头长度不表示某个时间段内的位移。X/Y 应使用相同长度单位，U/V 应使用相同速度单位。
- Flag 过滤仅掩蔽绘图值，不改变原始 `Data`；掩蔽节点周围的网格单元可能显示空白。不要仅凭截图把 Flag=0/1 推断为无效/有效。
- 不支持二进制 PLT/SZPLT、有限元网格、VARLOCATION（包括显式 NODAL 声明）、变量共享、被动变量、AUXDATA/几何文本记录或重复值简写。遇到这些扩展会报错，不能把本工具视为完整 Tecplot 文件解析器。
- 按整文件读取，适合截图这类小中型文件；超大文件可能需要流式解析。

## 文件与验证

本说明中的相对路径均以仓库内的 `matlab/` 目录为起点。图片输出目录和测试日志保留在本地，已通过仓库根目录的 `.gitignore` 排除。

| 文件 | 职责 |
|---|---|
| `read_tecplot_dat.m` | 解析和校验 DAT，返回统一数据结构 |
| `tecplot_variable.m` | 解析变量名称、单位后缀或列号 |
| `tecplot_grid.m` | 正确恢复结构网格排列 |
| `tecplot_plot.m` | 七种基础渲染模式与图片导出 |
| `tecplot_viewer.m` | 可交互前端 |
| `tecplot_cli.m` | 无交互批量导出入口 |
| `run_demo.m` / `make_demo_dat.m` | 运行示例 / 生成同规格模拟数据 |
| `tests/` | 解析、维度排列、异常输入、绘图和界面回归测试 |
| `examples/` | 合成示例 DAT |
| `output/` | 演示渲染图片和界面预览 |

运行验证：

```matlab
addpath('tests');
results = run_tests;
```

测试包含 POINT/BLOCK、多 Zone/K 层、153×79 网格方向、异常数据拒绝、Flag 掩蔽、七种渲染、降序流线、导出和界面调用。它们证明工具在合成/构造数据上的行为；不能替代对未提供原始文件的验收。

2026-09-22 在本机 MATLAB R2026a 上验证：**12/12 项测试通过**，包括自定义色标上下限、无效范围拒绝、模式切换和自动范围恢复；代码分析无提示；已生成并目视检查云图、流线、曲面和交互界面预览。完整测试输出见 `matlab-tests.log`。

2026-09-23 整体迁移至仓库的 `matlab/` 子目录后，重新通过 **12/12 项测试**，并确认 MATLAB 函数解析使用迁移后的路径。
