function filename = make_demo_dat(filename)
%MAKE_DEMO_DAT Write synthetic PIV data matching the screenshot's schema.
% The 153 x 79 points and nine variables are simulated, not measurements.
if nargin < 1
    filename = fullfile(fileparts(mfilename('fullpath')), 'examples', 'synthetic_piv.dat');
end
filename = char(filename);
if isfile(filename)
    error('tecplot:FileExists', 'Demo output already exists: %s', filename);
end
folder = fileparts(filename);
if ~isempty(folder) && ~isfolder(folder), mkdir(folder); end
[x,y] = meshgrid(253:4:861, 512:4:824);
a = (x-557)/150;
b = (y-668)/80;
e = exp(-(a.^2+b.^2));
u = 0.025 + 0.05*b.*e;
v = -0.035*a.*e;
w = zeros(size(x));
speed = hypot(u,v);
% Coordinates are mm; derivative scale factors below are in metres.
vorticity = -0.035/0.150*e.*(1-2*a.^2) - 0.05/0.080*e.*(1-2*b.^2);
flag = ones(size(x));
flag((x-680).^2 + (y-710).^2 < 22^2) = 0;
fields = {x,y,zeros(size(x)),u,v,w,speed,vorticity,flag};
data = zeros(numel(x), numel(fields));
for k = 1:numel(fields)
    t = fields{k}.';  % I/X varies fastest in POINT records.
    data(:,k) = t(:);
end
[fid,msg] = fopen(filename, 'w', 'n', 'UTF-8');
if fid < 0, error('tecplot:Write', 'Cannot open output: %s',msg); end
cleanup = onCleanup(@()fclose(fid));
fprintf(fid, 'TITLE="SYNTHETIC PIV DEMO - NOT MEASURED DATA"\n');
fprintf(fid, 'VARIABLES="X(mm)" "Y(mm)" "Z(mm)" "U(m/s)" "V(m/s)" "W(m/s)" "Velocity(m/s)" "Vorticity" "Flag"\n');
fprintf(fid, 'ZONE T="ZONE 1"\nI=153, J=79, K=1, F=POINT\n');
fprintf(fid, 'DT=(DOUBLE DOUBLE DOUBLE DOUBLE DOUBLE DOUBLE DOUBLE DOUBLE DOUBLE)\n');
fprintf(fid, '%.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g\n', data.');
end
