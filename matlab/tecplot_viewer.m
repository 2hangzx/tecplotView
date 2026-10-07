function app = tecplot_viewer(filename, varargin)
%TECPLOT_VIEWER Interactive Tecplot ASCII viewer (no App Designer needed).
% tecplot_viewer                  Open a viewer and choose a DAT file.
% tecplot_viewer('file.dat')      Load immediately.
% app = tecplot_viewer(...,'Visible','off') is useful for automation/tests.
if nargin < 1, filename = ''; end
p = inputParser;
addParameter(p, 'Visible', 'on');
addParameter(p, 'Folder', '');
addParameter(p, 'Recursive', false, @(x)islogical(x)&&isscalar(x));
parse(p, varargin{:});
if ~isempty(filename) && ~isempty(p.Results.Folder)
    error('tecplot:Source','请选择文件或文件夹，不能同时指定。');
end
d = [];
files = struct('Path',{},'RelativePath',{},'Status',{},'Message',{});
currentFile = ''; folderPath = ''; playing = false; playTimer = [];
scanning = false; scanGeneration = 0; updatingList = false;
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
browser = uipanel(controls,'Title','文件夹浏览与播放');
browser.Layout.Row = 1; browser.Layout.Column = [1 2];
browserGrid = uigridlayout(browser,[10 2]);
browserGrid.RowHeight = {32,30,25,110,28,28,30,30,28,38};
browserGrid.ColumnWidth = {'1x','1x'}; browserGrid.Padding = [4 4 4 4];
browserGrid.RowSpacing=3;
folderLabel = uilabel(browserGrid,'Text','未选择文件夹','WordWrap','on');
folderLabel.Layout.Row=1; folderLabel.Layout.Column=[1 2];
chooseFolderButton = uibutton(browserGrid,'Text','选择文件夹','ButtonPushedFcn',@chooseFolder);
chooseFolderButton.Layout.Row=2; chooseFolderButton.Layout.Column=1;
refreshButton = uibutton(browserGrid,'Text','重新扫描','ButtonPushedFcn',@refreshFolder);
refreshButton.Layout.Row=2; refreshButton.Layout.Column=2;
recursive = uicheckbox(browserGrid,'Text','包含子文件夹','Value',p.Results.Recursive);
recursive.Layout.Row=3; recursive.Layout.Column=[1 2];
fileList = uilistbox(browserGrid,'Items',{'未扫描'},'ItemsData',0,'Multiselect','on','Value',0,'ValueChangedFcn',@fileSelected);
fileList.Layout.Row=4; fileList.Layout.Column=[1 2];
order = uidropdown(browserGrid,'Items',{'正序','倒序'},'ValueChangedFcn',@browserChanged);
order.Layout.Row=5; order.Layout.Column=[1 2];
scope = uidropdown(browserGrid,'Items',{'全部文件','选中文件'},'ValueChangedFcn',@browserChanged);
scope.Layout.Row=6; scope.Layout.Column=[1 2];
previousButton = uibutton(browserGrid,'Text','上一文件','ButtonPushedFcn',@(~,~)stepFile(-1));
previousButton.Layout.Row=7; previousButton.Layout.Column=1;
nextButton = uibutton(browserGrid,'Text','下一文件','ButtonPushedFcn',@(~,~)stepFile(1));
nextButton.Layout.Row=7; nextButton.Layout.Column=2;
playButton = uibutton(browserGrid,'Text','播放','Enable','off','ButtonPushedFcn',@togglePlay);
playButton.Layout.Row=8; playButton.Layout.Column=1;
pauseButton = uibutton(browserGrid,'Text','暂停','ButtonPushedFcn',@(~,~)pausePlayback());
pauseButton.Layout.Row=8; pauseButton.Layout.Column=2;
interval = uieditfield(browserGrid,'numeric','Value',0.5,'Limits',[0 Inf],'LowerLimitInclusive','off','ValueChangedFcn',@browserChanged);
interval.Tooltip='间隔（秒）：显示完成后到加载下一文件的等待时间';
interval.Layout.Row=9; interval.Layout.Column=1;
loop = uicheckbox(browserGrid,'Text','循环播放','ValueChangedFcn',@browserChanged);
loop.Layout.Row=9; loop.Layout.Column=2;
browserHint = uilabel(browserGrid,'Text','Ctrl / Shift 多选；列表顺序不代表物理时间。','WordWrap','on');
browserHint.Layout.Row=10; browserHint.Layout.Column=[1 2];
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
% Move existing drawing controls below the file browser, keeping row helpers.
children = controls.Children;
for childIndex = 1:numel(children)
    if children(childIndex) ~= browser
        children(childIndex).Layout.Row = children(childIndex).Layout.Row + 1;
    end
end
controls.RowHeight = [{450}, controls.RowHeight];
freezeButton = uibutton(controls,'Text','固定当前色标范围','Enable','off','ButtonPushedFcn',@freezeLimits);
freezeButton.Layout.Row=23; freezeButton.Layout.Column=[1 2];
controls.RowHeight{23}=30;
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
app.ScanFolder=@scanFolder; app.SelectFile=@selectFile; app.Play=@play;
app.Pause=@pausePlayback; app.Step=@stepFile; app.GetSequence=@getSequence;
app.Close=@()delete(fig);
app.Controls.FileList=fileList; app.Controls.Recursive=recursive;
app.Controls.Order=order; app.Controls.Scope=scope; app.Controls.Interval=interval;
app.Controls.Loop=loop; app.Controls.Play=playButton; app.Controls.FreezeCLim=freezeButton;
fig.DeleteFcn=@closeResources;
if ~isempty(filename)
    try
        loadFile(filename);
    catch err
        delete(fig);
        rethrow(err);
    end
end
if ~isempty(p.Results.Folder)
    try
        scanFolder(p.Results.Folder);
    catch err
        delete(fig); rethrow(err);
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

    function loadFile(path, preserve, fromCollection)
        if nargin<2, preserve=false; end
        if nargin<3, fromCollection=false; end
        if ~fromCollection, pausePlayback(); currentFile=''; end
        if preserve && ~isempty(d)
            selected = variable.Value;
            mapping = [xvar.Value,yvar.Value,uvar.Value,vvar.Value];
            oldZone = zone.Value; oldK = kSlice.Value;
            oldFlags = flags.Value; oldAuto = autoLimits.Value;
            oldMode = mode.Value;
            oldLimits = [lowerLimit.Value,upperLimit.Value];
        end
        status.Text = '正在读取并检查数据…'; drawnow limitrate nocallbacks;
        candidate = read_tecplot_dat(path);
        if preserve && ~isempty(d)
            if oldZone>numel(candidate.Zones) || oldK>candidate.Zones(oldZone).K
                error('tecplot:Selection','新文件没有所选 Zone / K 层；请单独打开文件重新配置。');
            end
            required = [selected,mapping]; restored = required;
            for index=1:numel(required)
                if required(index)==0, continue; end
                name = d.Variables{required(index)};
                match = find(strcmp(candidate.Variables,name),1);
                if isempty(match)
                    error('tecplot:Variable','新文件缺少已选变量 %s；请单独打开文件重新配置。',name);
                end
                restored(index)=match;
            end
        end
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
        if preserve
            variable.Value=restored(1);
            for index=1:4, maps{index}.Value=restored(index+1); end
            zone.Value=oldZone; kSlice.Value=oldK;
            flags.Value=oldFlags; autoLimits.Value=oldAuto;
            lowerLimit.Value=oldLimits(1); upperLimit.Value=oldLimits(2);
            mode.Value=oldMode;
        end
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
        pausePlayback();
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
        updateLimitControls();
        status.Text = sprintf('%s | %d × %d × %d | %d 个点 | %s | K=%d', ...
            z.Name, z.I,z.J,z.K,size(z.Data,1),z.Packing,kSlice.Value);
    end

    function updateLimitControls()
        enabled = ~isempty(d) && ~ismember(mode.Value, {'quiver','mesh'});
        autoLimits.Enable = matlab.lang.OnOffSwitchState(enabled);
        manual = enabled && ~autoLimits.Value;
        lowerLimit.Enable = matlab.lang.OnOffSwitchState(manual);
        upperLimit.Enable = matlab.lang.OnOffSwitchState(manual);
        freezeButton.Enable = matlab.lang.OnOffSwitchState(enabled && strcmp(saveButton.Enable,'on'));
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
        pausePlayback();
        saveButton.Enable = 'off';
        status.Text = ['错误：', err.message];
        if strcmp(fig.Visible, 'on'), uialert(fig,err.message,'读取 / 绘图失败'); end
    end

    function chooseFolder(~,~)
        path=uigetdir;
        if isequal(path,0), return; end
        try, scanFolder(path); catch err, showError(err); end
    end

    function refreshFolder(~,~)
        if isempty(folderPath), return; end
        try, scanFolder(folderPath); catch err, showError(err); end
    end

    function scanFolder(path)
        pausePlayback(); scanGeneration=scanGeneration+1;
        generation=scanGeneration; scanning=true; playButton.Enable='off';
        try
            result=tecplot_scan_dat(path,'Recursive',recursive.Value, ...
                'ProgressFcn',@progress,'CancelFcn',@cancelled);
        catch err
            if isvalid(fig) && generation==scanGeneration
                scanning=false; playButton.Enable=matlab.lang.OnOffSwitchState(~isempty(files));
            end
            rethrow(err);
        end
        if result.Cancelled || ~isvalid(fig) || generation~=scanGeneration, return; end
        scanning=false; files=result.Files; folderPath=result.Folder; currentFile='';
        folderLabel.Text=folderPath;
        updateFileList(false);
        playButton.Enable=matlab.lang.OnOffSwitchState(~isempty(files));
        status.Text=sprintf('扫描完成：%d 个 DAT 文件。请选择文件绘图。',numel(files));
        if ~isempty(result.Warnings)
            status.Text=sprintf('%s %d 个扫描提示：%s',status.Text,numel(result.Warnings),result.Warnings{1});
        end
        function progress(count)
            if isvalid(fig), status.Text=sprintf('正在扫描：发现 %d 个 DAT 文件…',count); end
            drawnow limitrate;
        end
        function yes=cancelled()
            yes=~isvalid(fig) || generation~=scanGeneration;
        end
    end

    function ids=orderedIds(selectedOnly)
        if nargin<1, selectedOnly=strcmp(scope.Value,'选中文件'); end
        sorted=tecplot_sort_files(files,strcmp(order.Value,'倒序'));
        ids=zeros(1,numel(sorted));
        for index=1:numel(sorted)
            ids(index)=find(strcmp({files.RelativePath},sorted(index).RelativePath),1);
        end
        if selectedOnly, ids=ids(ismember(ids,fileList.Value)); end
    end

    function updateFileList(keepSelection)
        updatingList=true; selected=fileList.Value;
        if isempty(files)
            fileList.Items={'没有 DAT 文件'}; fileList.ItemsData=0; fileList.Value=0;
        else
            ids=orderedIds(false);
            fileList.Items=arrayfun(@(n)sprintf('%s [%s]',files(n).RelativePath,files(n).Status),ids,'UniformOutput',false);
            fileList.ItemsData=ids;
            if keepSelection
                fileList.Value=selected(ismember(selected,ids));
            else
                fileList.Value=[];
            end
        end
        updatingList=false;
    end

    function browserChanged(~,~)
        pausePlayback(); updateFileList(true);
    end

    function fileSelected(~,event)
        if updatingList || scanning, return; end
        pausePlayback(); ids=fileList.Value;
        if isempty(ids) || all(ids==0), return; end
        added=setdiff(ids,event.PreviousValue,'stable');
        if isempty(added), return; end
        selectFile(added(end));
    end

    function ok=selectFile(id)
        pausePlayback();
        if ischar(id) || isstring(id)
            id=find(strcmp({files.RelativePath},char(id)),1);
        end
        if isempty(id) || ~isscalar(id) || id<1 || id>numel(files)
            error('tecplot:FileSelection','请选择文件列表中的文件。');
        end
        ok=loadItem(id);
    end

    function ok=loadItem(id)
        ok=false;
        try
            loadFile(files(id).Path,~isempty(currentFile),true);
            drawnow limitrate nocallbacks;
            currentFile=files(id).RelativePath;
            files(id).Status='已读取'; files(id).Message='';
            updateFileList(true);
            ids=orderedIds(); position=find(ids==id,1);
            if isempty(position)
                status.Text=sprintf('%s | %s',currentFile,status.Text);
            else
                status.Text=sprintf('%s | 第 %d / %d 个文件 | %s',currentFile,position,numel(ids),status.Text);
            end
            ok=true;
        catch err
            pausePlayback(); files(id).Status='读取失败'; files(id).Message=err.message;
            updateFileList(true); saveButton.Enable='off';
            status.Text=sprintf('已暂停：%s | %s',files(id).RelativePath,err.message);
        end
    end

    function target=nextId(direction,wrap)
        if nargin<2, wrap=false; end
        ids=orderedIds(); target=[];
        if isempty(ids), return; end
        position=find(strcmp({files(ids).RelativePath},currentFile),1);
        if isempty(position)
            if direction>0, target=ids(1); else, target=ids(end); end
            return
        end
        position=position+direction;
        if wrap, position=mod(position-1,numel(ids))+1; end
        if position>=1 && position<=numel(ids), target=ids(position); end
    end

    function stepFile(direction)
        pausePlayback(); if scanning, return; end
        target=nextId(direction);
        if ~isempty(target), loadItem(target); end
    end

    function togglePlay(~,~)
        if playing, pausePlayback(); else, play(); end
    end

    function play()
        if scanning || playing || ~isvalid(fig), return; end
        if ~isfinite(interval.Value) || interval.Value<=0
            status.Text='播放失败：间隔必须为大于 0 的有限秒数。'; return
        end
        ids=orderedIds();
        if isempty(ids)
            status.Text='没有可播放的文件；请选择文件或更改播放范围。'; return
        end
        if ~any(strcmp({files(ids).RelativePath},currentFile))
            if ~loadItem(ids(1)), return; end
        end
        playing=true; playButton.Text='暂停'; schedulePlayback();
    end

    function schedulePlayback()
        if ~playing || ~isvalid(fig), return; end
        playTimer=timer('ExecutionMode','singleShot','StartDelay',max(.001,interval.Value), ...
            'BusyMode','drop','TimerFcn',@playTick,'ErrorFcn',@timerError);
        start(playTimer);
    end

    function playTick(source,~)
        playTimer=[];
        if isvalid(source), stop(source); delete(source); end
        if ~playing || ~isvalid(fig), return; end
        target=nextId(1,loop.Value);
        if isempty(target)
            pausePlayback(); status.Text=[status.Text,' | 播放结束'];
        elseif loadItem(target)
            schedulePlayback();
        end
    end

    function timerError(~,~)
        pausePlayback();
        if isvalid(fig), status.Text='播放失败：定时回调发生错误，已暂停。'; end
    end

    function pausePlayback()
        playing=false;
        if ~isempty(playTimer) && isvalid(playTimer)
            pendingTimer=playTimer; playTimer=[];
            stop(pendingTimer); delete(pendingTimer);
        end
        playTimer=[];
        if isvalid(playButton), playButton.Text='播放'; end
    end

    function value=getSequence()
        value=struct('Folder',folderPath,'Files',files,'Current',currentFile, ...
            'Playing',playing,'Scanning',scanning,'Timer',playTimer);
    end

    function freezeLimits(~,~)
        if isempty(d) || ismember(mode.Value,{'quiver','mesh'}), return; end
        lowerLimit.Value=ax.CLim(1); upperLimit.Value=ax.CLim(2);
        autoLimits.Value=false; redraw([],[]);
    end

    function closeResources(~,~)
        scanGeneration=scanGeneration+1; pausePlayback();
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
