function result = tecplot_scan_dat(folder, varargin)
%TECPLOT_SCAN_DAT Discover DAT files; a collection need not be a time series.
% Header hints are not full validation. read_tecplot_dat validates on load.
p = inputParser;
addParameter(p,'Recursive',false,@(x)islogical(x)&&isscalar(x));
addParameter(p,'ProgressFcn',[],@(x)isempty(x)||isa(x,'function_handle'));
addParameter(p,'CancelFcn',[],@(x)isempty(x)||isa(x,'function_handle'));
parse(p,varargin{:});
if ~isfolder(folder), error('tecplot:Folder','文件夹不存在：%s',folder); end
folder = char(java.io.File(char(folder)).getCanonicalPath());
files = struct('Path',{},'RelativePath',{},'Status',{},'Message',{});
warnings = {}; pending = {folder}; cancelled = false;
while ~isempty(pending)
    if shouldCancel(), cancelled = true; break; end
    directory = pending{end}; pending(end) = [];
    try
        entries = dir(directory);
    catch err
        if strcmp(directory,folder), rethrow(err); end
        warnings{end+1} = sprintf('%s: %s',directory,err.message); %#ok<AGROW>
        continue
    end
    for n = 1:numel(entries)
        if shouldCancel(), cancelled = true; break; end
        entry = entries(n);
        if ismember(entry.name,{'.','..'}), continue; end
        path = fullfile(directory,entry.name);
        try
            if ispc
                if bitand(int32(System.IO.File.GetAttributes(path)),1024) ~= 0, continue; end
            else
                canonical = char(java.io.File(path).getCanonicalPath());
                if ~strcmp(canonical,path), continue; end
            end
        catch err
            warnings{end+1} = sprintf('%s: %s',path,err.message); %#ok<AGROW>
            continue
        end
        if entry.isdir
            if p.Results.Recursive, pending{end+1} = path; end %#ok<AGROW>
        else
            [~,~,extension] = fileparts(path);
            if ~strcmpi(extension,'.dat'), continue; end
            prefix=folder;
            if prefix(end)~=filesep, prefix=[prefix,filesep]; end
            relative = strrep(path(numel(prefix)+1:end),'\','/');
            record = struct('Path',path,'RelativePath',relative,'Status','待完整验证','Message','');
            fid = fopen(path,'rb');
            if fid < 0
                record.Status = '读取失败'; record.Message = '无法打开文件';
            else
                cleanup = onCleanup(@()fclose(fid));
                head = fread(fid,65536,'*uint8').';
                clear cleanup
                text = native2unicode(head,'UTF-8');
                text = regexprep(text,'"[^"\n]*"|#[^\n]*',' ');
                if numel(head)>=5 && strcmp(char(head(1:5)),'#!TDV')
                    record.Status = '表头提示'; record.Message = '二进制 Tecplot 不受支持';
                elseif isempty(regexpi(text,'\<VARIABLES\s*=')) || isempty(regexpi(text,'\<ZONE\>'))
                    record.Status = '表头提示'; record.Message = '前 64 KiB 未识别出 VARIABLES / ZONE；选择后完整验证';
                end
            end
            files(end+1) = record; %#ok<AGROW>
        end
        if ~isempty(p.Results.ProgressFcn), p.Results.ProgressFcn(numel(files)); end
    end
    if cancelled, break; end
end
files = tecplot_sort_files(files);
result = struct('Folder',folder,'Files',files,'Warnings',{warnings},'Cancelled',cancelled);

    function yes = shouldCancel()
        yes = ~isempty(p.Results.CancelFcn) && p.Results.CancelFcn();
    end
end
