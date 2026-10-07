# Python 移植与功能验证记录

## 2026-10-07：文件集合浏览与播放

在原有项目独立 `.venv` 中验证，没有新增运行依赖。执行 `python -m pytest -q --require-gui --junitxml=output/test-results.xml`：**76 passed，0 skipped**，耗时 25.36 秒。扫描和界面测试覆盖一级／递归目录、大小写扩展名、相对路径、自然排序、目录链接／junction 不跟随、表头提示、手动选文件、全体／多选范围、倒序、真实定时播放、末尾停止、循环、暂停、关闭和取消／替换扫描。

连续文件采用合成数据；验证变量列重新排序时按名称恢复，固定／手动色标与 Flag 保留，损坏文件、缺少变量或 Zone／K 层时暂停。扫描不会自动加载文件，文件集合不被认定为物理时间序列。原有单文件、七种绘图和无桌面 CLI 测试继续通过。

同仓库 MATLAB R2026a：原有 12 项和新增前 5 项测试一起通过；追加 Zone／K 不兼容测试单独通过，共 **18 项**，没有失败或未完成测试。真实 MATLAB timer 的末尾停止、循环、暂停和关闭清理均已验证。

源码包与 wheel 已重建。独立 wheel 安装验证继续通过，并扩展验证 `scan_dat`、真实 GUI 扫描／文件切换、固定色标、播放回调和关闭清理。此验证仍复用本机第三方依赖，不是免 Python 的独立程序。物理时间没有推断；播放间隔为显示完成后的等待时间，不保证严格帧率。

以下保留 2026-09-23 的首次移植验证记录；当时的数值对照不是本次重新执行的结果。

验证日期：2026-09-23。所有实验数据均为合成样本；没有截图中的原始完整 DAT 文件。

## 环境

Windows；Python 3.12.14；NumPy 2.5.3；Matplotlib 3.11.2；Tcl/Tk 8.6.12；pytest 9.1.1。对照实现为同仓库 MATLAB R2026a 版本。依赖快照保存在 `requirements-tested.txt`。其他操作系统和 Python 版本未实机验证。

## 回归测试

执行 `python -m pytest -q --require-gui --junitxml=output/test-results.xml`，结果 **65 passed，0 skipped**。覆盖内容包括：

- POINT/BLOCK、多 Zone、K 层、跨行表头、注释、BOM、D 指数、NaN/Inf。
- I 最快的数据顺序、J/I/K 网格恢复及合成场数值。
- 不支持格式、坏表头、截断/多余数值和无效参数的拒绝。
- 七种绘图、Flag 掩蔽、恒定场、无 W 的速度模、降序和非均匀流线。
- 色标上下限、端点颜色、自动恢复、无效范围保留旧图但阻止导出。
- 真实 Tk 控件回调、2D/3D 切换、换文件、列映射、窗口关闭。
- 无显示环境的 CLI、JSON 元数据、错误退出码、PNG/PDF/JPEG/SVG 导出。

GUI 测试在隐藏的真实 Tk 窗口中执行；不是对界面的模拟。导出的四种主要模式预览已目视检查。

## MATLAB 数值对照

对同一份 153×79、9 列样本执行两种语言的读取/网格/绘图预处理：

| 比较对象 | 最大绝对差异 |
|---|---|
| 12,087×9 原始数据矩阵 | 0 |
| X、Y、U、V、Velocity、Vorticity、Flag 网格 | 0 |
| Flag 过滤后的 U/V | 0 |
| Flag 过滤后计算的速度模 | 5.551115123125783e-17 |

包括 NaN 位置在内通过 `rtol=1e-12, atol=1e-14` 比较。生成的参考矩阵和比较结果位于 `output/matlab_reference/`，可用 `validation/` 脚本复现。绘图外观不要求逐像素一致；配色、箭头自动缩放及流线算法差异已写入 README。

## 安装包

已通过标准构建流程，从源码包构建 wheel：

- `dist/tecplot_dat_viewer-0.1.0-py3-none-any.whl`
- `dist/tecplot_dat_viewer-0.1.0.tar.gz`

`validation/check_wheel.py` 将 wheel 安装到临时独立目录，在 Python `-I` 模式和源码树以外的工作目录中验证：实际导入来自 wheel 安装目录、内置样本可读、CLI 可导出 PNG、真实 Tk 界面可绘制并关闭。`pip check` 无依赖冲突。此验证复用已安装的第三方依赖，不等同于对所有系统环境的验证。
