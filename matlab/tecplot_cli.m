function info = tecplot_cli(inputFile, outputFile, varargin)
%TECPLOT_CLI Render/export without leaving a figure open; suited to -batch.
% tecplot_cli('flow.dat','flow.png','Mode','overlay','Variable','Velocity');
% Remaining options are passed to tecplot_plot. Output/Visible/Axes are owned
% by this wrapper; call tecplot_plot directly to manage an interactive figure.
if nargin < 2 || strlength(string(outputFile)) == 0
    error('tecplot:Output', 'Specify the output PNG/PDF/JPEG filename.');
end
for k = 1:2:numel(varargin)
    if any(strcmpi(varargin{k}, {'Output','Visible','Axes'}))
        error('tecplot:Option', 'tecplot_cli controls Output, Visible and Axes.');
    end
end
[fig,~,info] = tecplot_plot(inputFile, varargin{:}, 'Visible','off');
cleanup = onCleanup(@()close(fig));
exportgraphics(fig.CurrentAxes, char(outputFile), 'Resolution', 300);
fprintf('Exported: %s\n',char(outputFile));
end
