function grid = tecplot_grid(dataset, variable, zoneIndex)
%TECPLOT_GRID Return [J,I,K] data suitable for MATLAB XY plotting.
% G(j,i,k) corresponds to Tecplot node (i,j,k). I varies fastest in file.
if nargin < 3, zoneIndex = 1; end
validateattributes(zoneIndex, {'numeric'}, {'scalar','integer','>=',1,'<=',numel(dataset.Zones)});
column = tecplot_variable(dataset.Variables, variable);
z = dataset.Zones(zoneIndex);
grid = permute(reshape(z.Data(:,column), [z.I, z.J, z.K]), [2,1,3]);
end
