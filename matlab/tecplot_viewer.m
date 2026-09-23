function app = tecplot_viewer(filename, varargin)
%TECPLOT_VIEWER Interactive Tecplot ASCII viewer (no App Designer needed).
% tecplot_viewer                  Open a viewer and choose a DAT file.
% tecplot_viewer('file.dat')      Load immediately.
% app = tecplot_viewer(...,'Visible','off') is useful for automation/tests.
if nargin < 1, filename = ''; end
p = inputParser;
addParameter(p, 'Visible', 'on');
parse(p, varargin{:});
d = [];
fig = uifigure('Name', 'Tecplot DAT 查看器', 'Position', [80 80 1260 800], ...
    'Visible', p.Results.Visible, 'Color', [0.96 0.97 0.99]);
layout = uigridlayout(fig, [2 2]);
layout.ColumnWidth = {280, '1x'};
layout.RowHeight = {'1x', 44};
layout.Padding = [10 10 48 10]; % Reserve room for the colorbar label.
panel = uipanel(layout, 'Title', '数据与绘图');
panel.Layout.Row = 1; panel.Layout.Column = 1;
controls = uigridlayout(panel, [21 2]);
controls.ColumnWidth = {90, '1x'};
controls.RowHeight = [{32,32}, repmat({28},1,17), {34,90}];
controls.Scrollable = 'on';
controls.RowSpacing = 5;
openButton = uibutton(controls, 'Text', '打开 DAT 文件', 'ButtonPushedFcn', @chooseFile);
openButton.Layout.Row = 1; openButton.Layout.Column = [1 2];
demoButton = uibutton(controls, 'Text', '载入合成示例', 'ButtonPushedFcn', @loadDemo);
demoButton.Layout.Row = 2; demoButton.Layout.Column = [1 2];
zone = dropdown(3, '数据区 Zone', {'未载入'}, 1);
variable = dropdown(4, '显示变量', {'速度模（计算）'}, 0);
mode = dropdown(5, '绘图类型', {'云图 + 箭头','彩色云图','填色等值线','速度箭头','流线 + 云图','标量曲面','网格'}, ...
    {'overlay','heatmap','contour','quiver','streamlines','surface','mesh'});
kSlice = numeric(6, 'K 层', 1, [1 Inf]);
stride = numeric(7, '箭头/流线间隔', 5, [1 Inf]);
levels = numeric(8, '等值线级数', 24, [2 Inf]);
scale = numeric(9, '箭头缩放', 1.2, [0 Inf], false);
map = dropdown(10, '配色', {'parula','turbo','jet','gray','hot','cool'}, {'parula','turbo','jet','gray','hot','cool'});
autoLimits = uicheckbox(controls, 'Text', '自动色标范围', 'Value', true, 'ValueChangedFcn', @redraw);
autoLimits.Layout.Row = 11; autoLimits.Layout.Column = [1 2];
lowerLimit = numeric(12, '色标下限', 0, [-Inf Inf], false);
upperLimit = numeric(13, '色标上限', 1, [-Inf Inf], false);
lowerLimit.ValueDisplayFormat = '%.6g'; upperLimit.ValueDisplayFormat = '%.6g';
lowerLimit.Enable = 'off'; upperLimit.Enable = 'off';
lowerLimit.Tooltip = '取消自动色标范围后输入下限；必须小于上限。支持负数和科学计数法。';
upperLimit.Tooltip = '取消自动色标范围后输入上限；必须大于下限。超出范围的数据使用色标端点颜色。';
label(14, '保留 Flag 值');
flags = uieditfield(controls, 'text', 'Placeholder', '全部；或 1 / 1,2', 'ValueChangedFcn', @redraw);
flags.Layout.Row = 14; flags.Layout.Column = 2;
xvar = dropdown(15, 'X 坐标列', {'未载入'}, 1);
yvar = dropdown(16, 'Y 坐标列', {'未载入'}, 1);
uvar = dropdown(17, 'U 速度列', {'未载入'}, 1);
vvar = dropdown(18, 'V 速度列', {'未载入'}, 1);
reverseY = uicheckbox(controls, 'Text', 'Y 轴向下增大（图像坐标）', 'ValueChangedFcn', @redraw);
reverseY.Layout.Row = 19; reverseY.Layout.Column = [1 2];
saveButton = uibutton(controls, 'Text', '导出图片 / PDF', 'ButtonPushedFcn', @savePlot, 'Enable', 'off');
saveButton.Layout.Row = 20; saveButton.Layout.Column = [1 2];
details = uitextarea(controls, 'Editable', 'off', 'Value', {'支持 ASCII 有序网格。'; '默认保留全部 Flag。'; '打开文件后可缩放、平移。'});
details.Layout.Row = 21; details.Layout.Column = [1 2];
ax = uiaxes(layout);
ax.Layout.Row = 1; ax.Layout.Column = 2;
title(ax, '打开 .dat 文件，或载入合成示例');
status = uilabel(layout, 'Text', '就绪', 'WordWrap', 'on');
status.Layout.Row = 2; status.Layout.Column = [1 2];
app = struct('Figure', fig, 'Axes', ax, 'Load', @loadFile, 'Render', @render, ...
    'GetData', @getData, 'Controls', struct('Zone',zone,'Variable',variable,'Mode',mode, ...
    'KSlice',kSlice,'Stride',stride,'Levels',levels,'Scale',scale,'Colormap',map, ...
    'AutoCLim',autoLimits,'CLimMin',lowerLimit,'CLimMax',upperLimit, ...
    'Flags',flags,'ReverseY',reverseY,'X',xvar,'Y',yvar,'U',uvar,'V',vvar), ...
    'Status', status);
if ~isempty(filename)
    try
        loadFile(filename);
    catch err
        delete(fig);
        rethrow(err);
    end
end

    function h = label(row, text)
        h = uilabel(controls, 'Text', text);
        h.Layout.Row = row; h.Layout.Column = 1;
    end

    function h = dropdown(row, text, items, data)
        label(row, text);
        h = uidropdown(controls, 'Items', items, 'ItemsData', data, 'ValueChangedFcn', @redraw);
        h.Layout.Row = row; h.Layout.Column = 2;
    end

    function h = numeric(row, text, value, bounds, integerOnly)
        if nargin < 5, integerOnly = true; end
        label(row, text);
        h = uieditfield(controls, 'numeric', 'Value', value, 'Limits', bounds, 'ValueChangedFcn', @redraw);
        h.Layout.Row = row; h.Layout.Column = 2;
        if integerOnly, h.RoundFractionalValues = 'on'; end
    end

    function chooseFile(~,~)
        [name, folder] = uigetfile({'*.dat;*.tec;*.txt','Tecplot ASCII (*.dat, *.tec, *.txt)';'*.*','全部文件'});
        if isequal(name,0), return; end
        try
            loadFile(fullfile(folder,name));
        catch err
            showError(err);
        end
    end

    function loadDemo(~,~)
        try
            demoFile = fullfile(fileparts(mfilename('fullpath')), 'examples', 'synthetic_piv.dat');
            if ~isfile(demoFile), make_demo_dat(demoFile); end
            loadFile(demoFile);
        catch err
            showError(err);
        end
    end

    function loadFile(path)
        status.Text = '正在读取并检查数据…'; drawnow;
        candidate = read_tecplot_dat(path);
        d = candidate;
        zone.Items = arrayfun(@(n)sprintf('%d: %s', n, d.Zones(n).Name), 1:numel(d.Zones), 'UniformOutput', false);
        zone.ItemsData = 1:numel(d.Zones); zone.Value = 1;
        names = arrayfun(@(n)sprintf('%d: %s', n, d.Variables{n}), 1:numel(d.Variables), 'UniformOutput', false);
        variable.Items = [{'速度模（由 U,V,W 计算）'}, names];
        variable.ItemsData = 0:numel(names);
        storedSpeed = tecplot_variable(d.Variables, 'Velocity', false);
        if isempty(storedSpeed), variable.Value = 0; else, variable.Value = storedSpeed; end
        maps = {xvar,yvar,uvar,vvar}; keys = {'X','Y','U','V'};
        for n = 1:4
            maps{n}.Items = [{'请选择'}, names]; maps{n}.ItemsData = 0:numel(names);
            index = tecplot_variable(d.Variables, keys{n}, false);
            if isempty(index), index = 0; end
            maps{n}.Value = index;
        end
        if uvar.Value == 0 || vvar.Value == 0
            mode.Value = 'heatmap';
            if variable.Value == 0
                candidates = setdiff(1:numel(names),[xvar.Value,yvar.Value]);
                if isempty(candidates), candidates = 1; end
                variable.Value = candidates(1);
            end
        end
        flags.Value = ''; autoLimits.Value = true; kSlice.Value = 1;
        updateLimitControls();
        details.Value = {char(path); sprintf('%d 个变量 / %d 个数据区',numel(names),numel(d.Zones)); ...
            'Flag 含义由导出软件定义。'; '未设置过滤时保留全部点。'; '曲面高度为所选标量值。'};
        if xvar.Value == 0 || yvar.Value == 0
            cla(ax); saveButton.Enable = 'off';
            status.Text = '数据已读取。请从下拉菜单选择 X 和 Y 坐标列。';
        else
            render();
        end
    end

    function redraw(~,~)
        updateLimitControls();
        if isempty(d), return; end
        try
            render();
        catch err
            showError(err);
        end
    end

    function render()
        if isempty(d), error('tecplot:NoData','请先打开 DAT 文件。'); end
        saveButton.Enable = 'off';
        z = d.Zones(zone.Value);
        kSlice.Value = min(kSlice.Value, z.K);
        updateLimitControls();
        hasColorbar = ~ismember(mode.Value, {'quiver','mesh'});
        c = [];
        if hasColorbar && ~autoLimits.Value
            c = [lowerLimit.Value, upperLimit.Value];
            if any(~isfinite(c)) || c(1) >= c(2)
                error('tecplot:ColorLimits','色标上下限必须为有限数值，且下限必须小于上限。');
            end
        end
        validFlags = parseNumbers(flags.Value);
        selection = variable.Value;
        if selection == 0, selection = 'speed'; end
        tecplot_plot(d, 'Axes', ax, 'Mode', mode.Value, 'Variable', selection, ...
            'Zone', zone.Value, 'KSlice', kSlice.Value, 'Stride', stride.Value, ...
            'Levels', levels.Value, 'VectorScale', scale.Value, 'Colormap', map.Value, ...
            'CLim', c, 'ValidFlagValues', validFlags, 'ReverseY', reverseY.Value, ...
            'XVariable', xvar.Value, 'YVariable', yvar.Value, 'UVariable', uvar.Value, 'VVariable', vvar.Value);
        if hasColorbar && autoLimits.Value
            lowerLimit.Value = ax.CLim(1);
            upperLimit.Value = ax.CLim(2);
        end
        saveButton.Enable = 'on';
        status.Text = sprintf('%s | %d × %d × %d | %d 个点 | %s | K=%d', ...
            z.Name, z.I,z.J,z.K,size(z.Data,1),z.Packing,kSlice.Value);
    end

    function updateLimitControls()
        enabled = ~isempty(d) && ~ismember(mode.Value, {'quiver','mesh'});
        autoLimits.Enable = matlab.lang.OnOffSwitchState(enabled);
        manual = enabled && ~autoLimits.Value;
        lowerLimit.Enable = matlab.lang.OnOffSwitchState(manual);
        upperLimit.Enable = matlab.lang.OnOffSwitchState(manual);
    end

    function current = getData()
        % A nested function observes later loads; an anonymous @()d would
        % capture the empty dataset at the time the app struct was created.
        current = d;
    end

    function savePlot(~,~)
        [name, folder] = uiputfile({'*.png','PNG 图片';'*.pdf','PDF';'*.jpg','JPEG 图片'}, '导出当前图', 'tecplot.png');
        if isequal(name,0), return; end
        try
            exportgraphics(ax, fullfile(folder,name), 'Resolution', 300);
            status.Text = ['已导出：', fullfile(folder,name)];
        catch err
            showError(err);
        end
    end

    function showError(err)
        saveButton.Enable = 'off';
        status.Text = ['错误：', err.message];
        if strcmp(fig.Visible, 'on'), uialert(fig,err.message,'读取 / 绘图失败'); end
    end
end

function values = parseNumbers(text)
text = strtrim(text);
if isempty(text), values = []; return; end
tokens = regexp(text, '[,;\s]+', 'split');
values = str2double(tokens);
if any(~isfinite(values))
    error('tecplot:NumericInput', '请输入用空格或逗号分隔的有限数值。');
end
end
