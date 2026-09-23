function index = tecplot_variable(variables, selection, required)
%TECPLOT_VARIABLE Resolve a column number, exact name, or unit-free name.
% A missing optional variable returns []; ambiguous names always fail.
if nargin < 3, required = true; end
if isnumeric(selection)
    if isscalar(selection) && isfinite(selection) && selection == fix(selection) ...
            && selection >= 1 && selection <= numel(variables)
        index = selection;
        return
    end
    error('tecplot:Variable', 'Variable index must be between 1 and %d.', numel(variables));
end
selection = char(selection);
index = find(strcmpi(variables, selection));
if isempty(index)
    bare = regexprep(variables, '\s*[\(\[].*$', '');
    index = find(strcmpi(strtrim(bare), strtrim(selection)));
end
if numel(index) > 1
    error('tecplot:Variable', 'Ambiguous variable "%s"; use its full name or column number.', selection);
end
if isempty(index) && required
    error('tecplot:Variable', 'Variable "%s" not found. Available: %s', selection, strjoin(variables, ', '));
end
end
