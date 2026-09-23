function [fig, ax, info] = tecplot_plot(source, varargin)
%TECPLOT_PLOT Render an XY plane from a Tecplot ASCII file or parsed struct.
% tecplot_plot('file.dat','Mode','overlay','Variable','Velocity');
% tecplot_plot(D,'Mode','contour','Variable','Vorticity','Output','vort.png');
% Name/value options: Mode, Variable, Zone, KSlice, Axes, Visible, Output,
% Levels, Stride, VectorScale, CLim, Colormap, ReverseY, ValidFlagValues,
% XVariable, YVariable, UVariable, VVariable, WVariable, FlagVariable.
% Modes: heatmap, contour, quiver, overlay, streamlines, surface, mesh.
% Variable='speed' computes sqrt(U^2+V^2+W^2); omitted W is treated as zero.

p = inputParser;
addRequired(p, 'source');
addParameter(p, 'Mode', 'overlay');
addParameter(p, 'Variable', 'speed');
addParameter(p, 'Zone', 1, @positiveInteger);
addParameter(p, 'KSlice', 1, @positiveInteger);
addParameter(p, 'Axes', [], @(a)isempty(a) || isgraphics(a, 'axes'));
addParameter(p, 'Visible', 'on');
addParameter(p, 'Output', '');
addParameter(p, 'Levels', 24, @(x)positiveInteger(x) && x >= 2);
addParameter(p, 'Stride', 5, @positiveInteger);
addParameter(p, 'VectorScale', 1.2, @(x)isnumeric(x) && isscalar(x) && isfinite(x) && x >= 0);
addParameter(p, 'CLim', [], @(x)isempty(x) || (isnumeric(x) && numel(x)==2 && all(isfinite(x)) && x(1)<x(2)));
addParameter(p, 'Colormap', 'parula');
addParameter(p, 'ReverseY', false, @(x)islogical(x) && isscalar(x));
addParameter(p, 'ValidFlagValues', [], @(x)isnumeric(x) && (isempty(x) || isvector(x)) && all(isfinite(x)));
addParameter(p, 'XVariable', 'X');
addParameter(p, 'YVariable', 'Y');
addParameter(p, 'UVariable', 'U');
addParameter(p, 'VVariable', 'V');
addParameter(p, 'WVariable', 'W');
addParameter(p, 'FlagVariable', 'Flag');
parse(p, source, varargin{:});
o = p.Results;
mode = validatestring(o.Mode, {'heatmap','contour','quiver','overlay','streamlines','surface','mesh'});
visible = validatestring(o.Visible, {'on','off'});
if ischar(source) || isstring(source)
    d = read_tecplot_dat(source);
else
    d = source;
end
if o.Zone > numel(d.Zones)
    error('tecplot:Zone', 'Zone %d does not exist.', o.Zone);
end
z = d.Zones(o.Zone);
if o.KSlice > z.K
    error('tecplot:Slice', 'KSlice must be between 1 and %d.', z.K);
end
if z.I < 2 || z.J < 2
    error('tecplot:PlotDimensions', 'XY rendering needs I >= 2 and J >= 2.');
end
xi = tecplot_variable(d.Variables, o.XVariable);
yi = tecplot_variable(d.Variables, o.YVariable);
x = getSlice(xi);
y = getSlice(yi);
if any(~isfinite(x(:))) || any(~isfinite(y(:)))
    error('tecplot:Coordinates', 'X/Y coordinates must be finite.');
end
if max(x(:)) == min(x(:)) || max(y(:)) == min(y(:))
    error('tecplot:Coordinates', 'This XY plane must span both X and Y.');
end
validFlag = true(size(x));
if ~isempty(o.ValidFlagValues)
    flag = getSlice(tecplot_variable(d.Variables, o.FlagVariable));
    validFlag = ismember(flag, o.ValidFlagValues);
end
derivedSpeed = (ischar(o.Variable) || isstring(o.Variable)) && strcmpi(o.Variable, 'speed');
needVectors = ismember(mode, {'quiver','overlay','streamlines'});
needScalar = ~ismember(mode, {'quiver','mesh'});
u = []; v = []; scalar = []; scalarName = '';
if needVectors || (needScalar && derivedSpeed)
    ui = tecplot_variable(d.Variables, o.UVariable);
    vi = tecplot_variable(d.Variables, o.VVariable);
    u = getSlice(ui);
    v = getSlice(vi);
end
if needScalar
    if derivedSpeed
        wi = tecplot_variable(d.Variables, o.WVariable, false);
        w = zeros(size(u));
        if ~isempty(wi), w = getSlice(wi); end
        scalar = hypot(hypot(u,v), w);
        unit = regexp(d.Variables{ui}, '(\([^)]*\)|\[[^]]*\])\s*$', 'match', 'once');
        scalarName = ['Speed ', unit];
    else
        ci = tecplot_variable(d.Variables, o.Variable);
        scalar = getSlice(ci);
        scalarName = d.Variables{ci};
    end
    scalar(~validFlag | ~isfinite(scalar)) = NaN;
    if ~any(isfinite(scalar(:)))
        error('tecplot:NoValidData', 'No finite scalar values remain after filtering.');
    end
end
if needVectors
    invalid = ~validFlag | ~isfinite(u) | ~isfinite(v);
    u(invalid) = NaN;
    v(invalid) = NaN;
    if ~any(isfinite(u(:)))
        error('tecplot:NoValidData', 'No finite vectors remain after filtering.');
    end
end
% Compute streamlines before changing axes so unsupported grids give a clean error.
vertices = {};
if strcmp(mode, 'streamlines')
    [sx, sy, su, sv] = rectilinear(x, y, u, v);
    nx = min(18, max(3, ceil(z.I/o.Stride)));
    ny = min(12, max(3, ceil(z.J/o.Stride)));
    [seedsX, seedsY] = meshgrid(linspace(sx(1),sx(end),nx), linspace(sy(1),sy(end),ny));
    vertices = stream2(sx, sy, su, sv, seedsX, seedsY, [0.15, 3000]);
end
map = o.Colormap;
if ischar(map) || isstring(map)
    map = validatestring(map, {'parula','turbo','jet','hot','cool','gray','spring','summer','autumn','winter','bone','copper','pink'});
    map = feval(map, 256);
else
    validateattributes(map, {'numeric'}, {'2d','ncols',3,'nonempty','finite','>=',0,'<=',1});
end
if isempty(o.Axes)
    fig = figure('Name', 'Tecplot MATLAB Viewer', 'Color', 'w', ...
        'Visible', visible, 'Position', [100 100 1100 700]);
    ax = axes('Parent', fig);
else
    ax = o.Axes;
    fig = ancestor(ax, 'figure');
end
cla(ax, 'reset');
colorbar(ax, 'off');
hold(ax, 'on');
restoreHold = onCleanup(@()hold(ax, 'off'));
switch mode
    case {'heatmap','streamlines'}
        surf(ax, x, y, zeros(size(x)), scalar, 'EdgeColor', 'none', 'FaceColor', 'interp');
        view(ax, 2);
    case {'contour','overlay'}
        finiteC = scalar(isfinite(scalar));
        if max(finiteC) == min(finiteC)
            % contourf has no filled bands for a constant field.
            surf(ax, x, y, zeros(size(x)), scalar, 'EdgeColor', 'none', 'FaceColor', 'flat');
            view(ax, 2);
        else
            contourf(ax, x, y, scalar, o.Levels, 'LineColor', 'none');
        end
    case 'surface'
        surf(ax, x, y, scalar, scalar, 'EdgeColor', 'none', 'FaceColor', 'interp');
        view(ax, 3);
        zlabel(ax, scalarName, 'Interpreter', 'none');
    case 'mesh'
        plane = zeros(size(x));
        plane(~validFlag) = NaN;
        surf(ax, x, y, plane, 'FaceColor', 'none', 'EdgeColor', [0.2 0.35 0.5]);
        view(ax, 2);
end
if ismember(mode, {'quiver','overlay'})
    rows = 1:o.Stride:z.J;
    cols = 1:o.Stride:z.I;
    quiver(ax, x(rows,cols), y(rows,cols), u(rows,cols), v(rows,cols), ...
        o.VectorScale, 'Color', [0.12 0.12 0.12], 'LineWidth', 0.8);
    view(ax, 2);
elseif strcmp(mode, 'streamlines')
    for k = 1:numel(vertices)
        xy = vertices{k};
        if size(xy,1) >= 2
            plot(ax, xy(:,1), xy(:,2), 'Color', [0.12 0.12 0.12], 'LineWidth', 0.8);
        end
    end
end
colormap(ax, map);
if needScalar
    cb = colorbar(ax);
    cb.Label.String = scalarName;
    cb.Label.Interpreter = 'none';
    if ~isempty(o.CLim), ax.CLim = o.CLim; end
end
if ~strcmp(mode, 'surface'), axis(ax, 'equal'); end
axis(ax, 'tight');
if ~strcmp(mode, 'surface')
    % Quiver tips may extend past the measured domain. Keep the plotted
    % footprint tied to the grid rather than autoscaling to arrow tips.
    xlim(ax, [min(x(:)),max(x(:))]);
    ylim(ax, [min(y(:)),max(y(:))]);
end
xlabel(ax, d.Variables{xi}, 'Interpreter', 'none');
ylabel(ax, d.Variables{yi}, 'Interpreter', 'none');
set(ax, 'YDir', 'normal', 'Box', 'on', 'FontSize', 11, 'Layer', 'top');
if o.ReverseY, set(ax, 'YDir', 'reverse'); end
titleParts = {d.Title, z.Name};
if ~isempty(scalarName), titleParts{end+1} = scalarName; end
titleText = strjoin(titleParts(~cellfun('isempty', titleParts)), ' | ');
if z.K > 1, titleText = sprintf('%s | K = %d', titleText, o.KSlice); end
if isfinite(z.SolutionTime), titleText = sprintf('%s | t = %g', titleText, z.SolutionTime); end
title(ax, titleText, 'Interpreter', 'none');
info = struct('Zone', o.Zone, 'KSlice', o.KSlice, 'Mode', mode, ...
    'X', x, 'Y', y, 'Scalar', scalar, 'U', u, 'V', v, ...
    'FlagMask', validFlag, 'ScalarName', scalarName);
if ~isempty(o.Output)
    drawnow;
    exportgraphics(ax, char(o.Output), 'Resolution', 300);
end

    function result = getSlice(column)
        allPlanes = tecplot_grid(d, column, o.Zone);
        result = allPlanes(:,:,o.KSlice);
    end
end

function ok = positiveInteger(x)
ok = isnumeric(x) && isscalar(x) && isfinite(x) && x >= 1 && x == fix(x);
end

function [xv, yv, u, v] = rectilinear(x, y, u, v)
% stream2 requires a monotonic meshgrid; preserve data when axes descend.
xv = x(1,:);
yv = y(:,1);
xtol = max(1,max(abs(x(:)))) * 1e-9;
ytol = max(1,max(abs(y(:)))) * 1e-9;
if any(abs(x - repmat(xv,size(x,1),1)) > xtol, 'all') || ...
        any(abs(y - repmat(yv,1,size(y,2))) > ytol, 'all')
    error('tecplot:StreamGrid', 'Streamlines require a rectilinear XY grid; use overlay for a curved grid.');
end
if all(diff(xv) < 0)
    xv = fliplr(xv); u = fliplr(u); v = fliplr(v);
end
if all(diff(yv) < 0)
    yv = flipud(yv); u = flipud(u); v = flipud(v);
end
if any(diff(xv) <= 0) || any(diff(yv) <= 0)
    error('tecplot:StreamGrid', 'Streamline X/Y axes must be strictly monotonic with no duplicate positions.');
end
end
