function files = tecplot_sort_files(files, reverse)
%TECPLOT_SORT_FILES Natural relative-path order; numeric runs compare by value.
if nargin<2, reverse=false; end
keys = cell(numel(files),1);
for n=1:numel(files)
    parts = regexp(lower(files(n).RelativePath),'[0-9]+|[^0-9]+','match');
    key = '';
    for k=1:numel(parts)
        part = parts{k};
        if all(part>='0' & part<='9')
            part = regexprep(part,'^0+(?=[0-9])','');
            key = [key,char(1),sprintf('%08d',length(part)),part,char(1)]; %#ok<AGROW>
        else
            key = [key,part]; %#ok<AGROW>
        end
    end
    keys{n} = key;
end
if isempty(files), return; end
[~,order] = sortrows([string(keys), string({files.RelativePath}.')],[1 2]);
if reverse, order = flipud(order); end
files = files(order);
end
