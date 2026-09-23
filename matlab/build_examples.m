function build_examples
%BUILD_EXAMPLES Generate synthetic sample data and visual previews.
root = fileparts(mfilename('fullpath'));
file = fullfile(root,'examples','synthetic_piv.dat');
if ~isfile(file), make_demo_dat(file); end
out = fullfile(root,'output');
if ~isfolder(out), mkdir(out); end
d = read_tecplot_dat(file);
fig = figure('Visible','off','Color','w','Position',[50 50 1400 900]);
cleanup = onCleanup(@()close(fig));
t = tiledlayout(fig,2,2,'TileSpacing','compact','Padding','compact');
modes = {'overlay','contour','streamlines','surface'};
vars = {'Velocity','Vorticity','Velocity','Velocity'};
titles = {'Velocity + vectors','Vorticity contours','Planar streamlines','Scalar height surface'};
for k = 1:4
    ax = nexttile(t);
    tecplot_plot(d,'Axes',ax,'Mode',modes{k},'Variable',vars{k},'Stride',6);
    title(ax,[titles{k}, ' (synthetic)']);
end
drawnow;
exportgraphics(t,fullfile(out,'demo_overview.png'),'Resolution',150);
tecplot_cli(file,fullfile(out,'velocity.png'),'Variable','Velocity','Mode','overlay');
tecplot_cli(file,fullfile(out,'vorticity.pdf'),'Variable','Vorticity','Mode','contour');
app = tecplot_viewer(file,'Visible','off');
cleanupApp = onCleanup(@()delete(app.Figure));
drawnow;
exportapp(app.Figure,fullfile(out,'viewer.png'));
fprintf('Demo artifacts: %s\n',out);
end
