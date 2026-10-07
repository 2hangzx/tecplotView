# Tecplot 数据可视化工具

Python 分支增加了独立的 [`python/`](python/) 包，支持桌面界面、命令行、Python API 和自定义色标上下限。安装、运行及与 MATLAB 的逐项对应见 [Python 使用说明](python/README.md)。

MATLAB 实现位于 [`matlab/`](matlab/)，包含 Tecplot ASCII 数据读取、交互查看、命令行绘图、自定义色标范围及图片导出。

两端均支持文件夹扫描、可选递归、自然排序、手动选文件和按间隔播放；可以保持固定色标跨文件比较。扫描结果是文件集合，不自动认定为物理时间序列。默认间隔 0.5 秒、不循环，读取或绘图失败时暂停。

## 快速运行

在 MATLAB 中进入本仓库的 `matlab` 目录：

```matlab
cd('D:\myDocuments\BUAA\tecplot\matlab');
run_demo
```

已有 DAT 文件可通过 `tecplot_viewer` 打开。完整参数和命令行示例见 [MATLAB 使用说明](matlab/README.md)。

## 目录

```text
tecplot/
├── README.md
├── .gitignore
├── python/             Python 包、桌面界面、CLI、测试和安装说明
└── matlab/
    ├── *.m             MATLAB 读取、绘图和界面入口
    ├── README.md       详细使用说明
    ├── tests/          回归测试
    ├── examples/       合成示例 DAT（纳入版本管理）
    └── output/         本地生成的图片和 PDF（Git 忽略）
```

## 验证

在 `matlab/` 目录中运行：

```matlab
addpath('tests');
run_tests
```

仓库保存源代码、说明、测试和合成示例。已有渲染结果和日志保留在 `matlab/` 下，生成的图片目录、测试日志及 MATLAB 自动保存文件不纳入版本管理。
