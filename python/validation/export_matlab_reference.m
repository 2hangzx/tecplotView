function export_matlab_reference
% Optional cross-language validation; not a Python runtime dependency.
pythonRoot = fileparts(fileparts(mfilename('fullpath')));
repoRoot = fileparts(pythonRoot);
addpath(fullfile(repoRoot, 'matlab'));
source = fullfile(pythonRoot, 'src', 'tecplot_viewer', 'data', 'synthetic_piv.dat');
out = fullfile(pythonRoot, 'output', 'matlab_reference');
if ~isfolder(out), mkdir(out); end
d = read_tecplot_dat(source);
writematrix(d.Zones(1).Data, fullfile(out, 'data.csv'));
for variable = {'X', 'Y', 'U', 'V', 'Velocity', 'Vorticity', 'Flag'}
    grid = tecplot_grid(d, variable{1});
    writematrix(grid, fullfile(out, [variable{1} '.csv']));
end
f = figure('Visible','off');
cleanup = onCleanup(@()close(f));
ax = axes(f);
[~,~,info] = tecplot_plot(d, 'Axes', ax, 'Variable', 'speed', 'ValidFlagValues', 1, 'CLim', [0 .06]);
writematrix(info.Scalar, fullfile(out, 'masked_speed.csv'));
writematrix(info.U, fullfile(out, 'masked_u.csv'));
writematrix(info.V, fullfile(out, 'masked_v.csv'));
fprintf('MATLAB reference arrays written to %s\n', out);
end
