function results = run_tests
%RUN_TESTS Reader, data orientation, rendering, export, and GUI smoke tests.
root = fileparts(fileparts(mfilename('fullpath')));
addpath(root);
results = runtests(fullfile(root,'tests','TestTecplot.m'));
disp(table(results));
assert(all([results.Passed]), 'tecplot:TestsFailed', 'One or more tests failed.');
end
