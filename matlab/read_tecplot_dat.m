function dataset = read_tecplot_dat(filename)
%READ_TECPLOT_DAT Read nodal, ordered Tecplot ASCII POINT/BLOCK data.
% D = READ_TECPLOT_DAT(FILE) preserves variable names and file node order.
% D.Zones(n).Data is [I*J*K, numberOfVariables], with I varying fastest.
% Explicit I/J/K dimensions are required. Unsupported features fail clearly.

filename = char(filename);
if ~isfile(filename)
    error('tecplot:FileNotFound', 'File not found: %s', filename);
end
raw = fileread(filename);
if startsWith(raw, '#!TDV') || any(raw == char(0))
    error('tecplot:BinaryFile', 'Use a Tecplot ASCII export, not a binary PLT/SZPLT file.');
end
raw = strrep(raw, char(65279), '');
if startsWith(raw, char([239 187 191]))
    raw = raw(4:end);
end
lines = regexp(raw, '\r\n|\n|\r', 'split');
for n = 1:numel(lines)
    lines{n} = strtrim(removeComment(lines{n}));
end
zoneStart = find(~cellfun('isempty', regexpi(lines, '^ZONE(?=\s|$)', 'once')));
if isempty(zoneStart)
    error('tecplot:MissingZone', 'No ZONE record was found.');
end
preamble = strjoin(lines(1:zoneStart(1)-1), newline);
[titleText, variables] = readPreamble(preamble);
nv = numel(variables);
zoneEnd = [zoneStart(2:end)-1, numel(lines)];
zones = struct('Name', {}, 'I', {}, 'J', {}, 'K', {}, 'Packing', {}, ...
    'SolutionTime', {}, 'StrandID', {}, 'Data', {}, 'Header', {});

for iz = 1:numel(zoneStart)
    first = zoneStart(iz);
    last = zoneEnd(iz);
    numericLine = [];
    for n = first+1:last
        if ~isempty(regexpi(lines{n}, '^[+\-]?(?:\d|\.\d|NaN(?=[,\s]|$)|Inf(?=[,\s]|$))', 'once'))
            numericLine = n;
            break
        end
    end
    if isempty(numericLine)
        error('tecplot:MissingData', 'Zone %d has no numeric data.', iz);
    end
    header = strjoin(lines(first:numericLine-1), ' ');
    z = readZoneHeader(header, nv, iz);
    body = strjoin(lines(numericLine:last), ' ');
    % Validate every token before sscanf: it otherwise silently stops at junk.
    body = strrep(body, ',', ' ');
    tokenPattern = '^[+\-]?(?:(?:\d+\.?\d*|\.\d+)(?:[eEdD][+\-]?\d+)?|[iI][nN][fF]|[nN][aA][nN])$';
    tokens = regexp(strtrim(body), '\s+', 'split');
    valid = ~cellfun('isempty', regexp(tokens, tokenPattern, 'once'));
    if ~all(valid)
        bad = tokens{find(~valid, 1)};
        error('tecplot:InvalidData', 'Zone %d: invalid/unsupported data token "%s".', iz, bad);
    end
    expected = z.I * z.J * z.K * nv;
    if numel(tokens) ~= expected
        error('tecplot:DataCount', ...
            'Zone %d needs %d values (%d x %d x %d nodes x %d variables), but has %d.', ...
            iz, expected, z.I, z.J, z.K, nv, numel(tokens));
    end
    values = sscanf(regexprep(body, '[dD]', 'E'), '%f');
    if numel(values) ~= expected
        error('tecplot:InvalidData', 'Zone %d: numeric conversion failed.', iz);
    end
    if strcmp(z.Packing, 'POINT')
        z.Data = reshape(values, nv, []).';
    else
        z.Data = reshape(values, [], nv);
    end
    zones(iz) = z;
end
dataset = struct('Title', titleText, 'Variables', {variables}, ...
    'Zones', zones, 'FileName', filename, 'Format', 'Tecplot ASCII ordered nodal');
end

function line = removeComment(line)
quoted = false;
for k = 1:numel(line)
    if line(k) == '"' && (k == 1 || line(k-1) ~= '\')
        quoted = ~quoted;
    elseif line(k) == '#' && ~quoted
        line = line(1:k-1);
        return
    end
end
end

function [titleText, variables] = readPreamble(text)
titleText = '';
variables = {};
[starts, ends, names] = regexpi(text, '(?m)^\s*(TITLE|VARIABLES|FILETYPE)\s*=', ...
    'start', 'end', 'tokens');
if isempty(starts) || ~isempty(strtrim(text(1:starts(1)-1)))
    error('tecplot:Header', 'Expected TITLE / VARIABLES / FILETYPE before the first ZONE.');
end
stops = [starts(2:end)-1, numel(text)];
seen = {};
for k = 1:numel(starts)
    key = upper(names{k}{1});
    if ismember(key, seen)
        error('tecplot:Header', 'Duplicate %s record.', key);
    end
    seen{end+1} = key; %#ok<AGROW>
    value = strtrim(text(ends(k)+1:stops(k)));
    switch key
        case 'TITLE'
            q = regexp(value, '^"(.*)"\s*,?$', 'tokens', 'once');
            if isempty(q), error('tecplot:Header', 'TITLE must be a quoted string.'); end
            titleText = q{1};
        case 'FILETYPE'
            if ~strcmpi(strtrim(strrep(value, ',', '')), 'FULL')
                error('tecplot:Unsupported', 'Only FILETYPE=FULL is supported.');
            end
        case 'VARIABLES'
            if contains(value, '"')
                q = regexp(value, '"([^"\r\n]+)"', 'tokens');
                residual = regexprep(value, '"[^"\r\n]+"', '');
                if ~isempty(regexprep(residual, '[\s,]', ''))
                    error('tecplot:Header', 'Invalid VARIABLES record or unsupported global record.');
                end
                variables = cellfun(@(c)c{1}, q, 'UniformOutput', false);
            else
                variables = regexp(value, '[^\s,]+', 'match');
                if any(contains(variables, '='))
                    error('tecplot:Header', 'Unsupported record in VARIABLES.');
                end
            end
    end
end
if isempty(variables)
    error('tecplot:MissingVariables', 'A nonempty VARIABLES record is required.');
end
end

function z = readZoneHeader(header, nv, iz)
text = regexprep(header, '^ZONE\s*', '', 'ignorecase');
pattern = '([A-Za-z][A-Za-z0-9_]*)\s*=\s*("[^"\r\n]*"|\([^)]*\)|[^\s,]+)';
pairs = regexp(text, pattern, 'tokens');
residual = regexprep(text, pattern, '');
if ~isempty(regexprep(residual, '[\s,]', ''))
    error('tecplot:Header', 'Zone %d has an unsupported/malformed header: %s', iz, residual);
end
meta = struct;
allowed = {'T','I','J','K','F','DATAPACKING','ZONETYPE','DT','SOLUTIONTIME','STRANDID'};
for k = 1:numel(pairs)
    key = upper(pairs{k}{1});
    if ~ismember(key, allowed)
        error('tecplot:Unsupported', 'Zone %d: %s is not supported (ordered, nodal, unshared data only).', iz, key);
    end
    if isfield(meta, key)
        error('tecplot:Header', 'Zone %d: duplicate %s.', iz, key);
    end
    meta.(key) = pairs{k}{2};
end
if isfield(meta, 'ZONETYPE') && ~strcmpi(meta.ZONETYPE, 'ORDERED')
    error('tecplot:Unsupported', 'Zone %d: only ZONETYPE=ORDERED is supported.', iz);
end
packing = 'BLOCK';
if isfield(meta, 'F'), packing = upper(meta.F); end
if isfield(meta, 'DATAPACKING')
    if isfield(meta, 'F') && ~strcmpi(meta.F, meta.DATAPACKING)
        error('tecplot:Header', 'Conflicting F and DATAPACKING in zone %d.', iz);
    end
    packing = upper(meta.DATAPACKING);
end
if ~ismember(packing, {'POINT','BLOCK'})
    error('tecplot:Unsupported', 'Zone %d: unsupported packing %s.', iz, packing);
end
if ~any(isfield(meta, {'I','J','K'}))
    error('tecplot:Dimensions', 'Zone %d: explicit I/J/K dimensions are required.', iz);
end
dims = ones(1,3);
keys = {'I','J','K'};
for k = 1:3
    if isfield(meta, keys{k})
        dims(k) = str2double(meta.(keys{k}));
    end
end
if any(~isfinite(dims) | dims < 1 | dims ~= fix(dims)) || prod(dims)*nv > flintmax
    error('tecplot:Dimensions', 'Zone %d: I/J/K must be positive, finite integers.', iz);
end
if isfield(meta, 'DT')
    types = regexp(upper(meta.DT), '[A-Z][A-Z0-9]*', 'match');
    if numel(types) ~= nv || ~all(ismember(types, {'DOUBLE','SINGLE','LONGINT','SHORTINT','BYTE','BIT'}))
        error('tecplot:Header', 'Zone %d: DT must specify one supported type per variable.', iz);
    end
end
name = sprintf('Zone %d', iz);
if isfield(meta, 'T'), name = strrep(meta.T, '"', ''); end
time = NaN;
strand = NaN;
if isfield(meta, 'SOLUTIONTIME')
    time = str2double(regexprep(meta.SOLUTIONTIME, '[dD]', 'E'));
    if ~isfinite(time), error('tecplot:Header', 'Invalid SOLUTIONTIME.'); end
end
if isfield(meta, 'STRANDID')
    strand = str2double(meta.STRANDID);
    if ~isfinite(strand) || strand < 0 || strand ~= fix(strand)
        error('tecplot:Header', 'Invalid STRANDID.');
    end
end
z = struct('Name', name, 'I', dims(1), 'J', dims(2), 'K', dims(3), ...
    'Packing', packing, 'SolutionTime', time, 'StrandID', strand, ...
    'Data', [], 'Header', header);
end
