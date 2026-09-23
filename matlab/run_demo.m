%RUN_DEMO Open a viewer with synthetic PIV data matching the screenshot.
projectRoot = fileparts(mfilename('fullpath'));
addpath(projectRoot);
demoFile = fullfile(projectRoot, 'examples', 'synthetic_piv.dat');
if ~isfile(demoFile), make_demo_dat(demoFile); end
tecplot_viewer(demoFile);
