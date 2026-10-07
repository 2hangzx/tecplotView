classdef TestFileCollection < matlab.unittest.TestCase
    properties
        WorkDir
    end
    methods(TestMethodSetup)
        function setup(test)
            test.WorkDir=tempname; mkdir(test.WorkDir);
            test.addTeardown(@()rmdir(test.WorkDir,'s'));
        end
    end
    methods(Test)
        function scanDepthHeadersAndOrder(test)
            test.write('file10.DAT',test.sample());
            test.write('file2.dat',test.sample());
            test.write('file01.dat',test.sample());
            test.write('ordinary.dat','ordinary text');
            test.write('binary.dat','#!TDV112');
            mkdir(fullfile(test.WorkDir,'child'));
            test.write(fullfile('child','file2.dat'),test.sample());
            result=tecplot_scan_dat(test.WorkDir);
            test.verifyEqual({result.Files.RelativePath},{'binary.dat','file01.dat','file2.dat','file10.DAT','ordinary.dat'});
            test.verifyEqual(result.Files(1).Status,'表头提示');
            test.verifyEqual(result.Files(2).Status,'待完整验证');
            nested=tecplot_scan_dat(test.WorkDir,'Recursive',true);
            test.verifyEqual(numel(nested.Files),6);
            test.verifyTrue(any(strcmp({nested.Files.RelativePath},'child/file2.dat')));
            empty=fullfile(test.WorkDir,'empty'); mkdir(empty);
            test.verifyEmpty(tecplot_scan_dat(empty).Files);
            test.verifyError(@()tecplot_scan_dat(fullfile(test.WorkDir,'missing')),'tecplot:Folder');
            stopped=tecplot_scan_dat(test.WorkDir,'CancelFcn',@()true);
            test.verifyTrue(stopped.Cancelled);
        end

        function browseAndSettingsRestoredByName(test)
            test.write('file2.dat',test.sample());
            test.write('file10.dat',test.swapped());
            app=tecplot_viewer('','Visible','off','Folder',test.WorkDir);
            test.addTeardown(@()delete(app.Figure));
            test.verifyEmpty(app.GetData());
            test.verifyEmpty(app.GetSequence().Current);
            test.verifyTrue(app.SelectFile(1));
            c=app.Controls; c.AutoCLim.Value=false;
            c.CLimMin.Value=0; c.CLimMax.Value=3; c.Flags.Value='1'; app.Render();
            app.Step(1);
            test.verifyEqual(app.GetSequence().Current,'file10.dat');
            test.verifyEqual(c.Variable.Value,6);
            test.verifyEqual(c.X.Value,2); test.verifyEqual(c.U.Value,4);
            test.verifyEqual(c.Flags.Value,'1'); test.verifyEqual(app.Axes.CLim,[0 3]);
            c.Order.Value='倒序'; c.Order.ValueChangedFcn(c.Order,[]);
            app.Step(1);
            test.verifyEqual(app.GetSequence().Current,'file2.dat');
            c.AutoCLim.Value=true; app.Render();
            c.FreezeCLim.ButtonPushedFcn(c.FreezeCLim,[]);
            limits=app.Axes.CLim;
            app.Step(-1);
            test.verifyEqual(app.Axes.CLim,limits);
        end

        function timerEndLoopPauseAndCleanup(test)
            test.write('file2.dat',test.sample()); test.write('file10.dat',test.swapped());
            app=tecplot_viewer('','Visible','off','Folder',test.WorkDir);
            test.addTeardown(@()test.closeApp(app));
            app.Controls.Interval.Value=.5; app.Play();
            start=tic;
            while app.GetSequence().Playing && toc(start)<10, drawnow; pause(.02); end
            test.verifyFalse(app.GetSequence().Playing);
            test.verifyEqual(app.GetSequence().Current,'file10.dat');
            test.verifyTrue(contains(app.Status.Text,'播放结束'));
            app.Controls.Loop.Value=true; app.Play();
            start=tic;
            while strcmp(app.GetSequence().Current,'file10.dat') && toc(start)<10, drawnow; pause(.02); end
            test.verifyEqual(app.GetSequence().Current,'file2.dat');
            app.Pause(); test.verifyEmpty(app.GetSequence().Timer);
            app.Controls.Interval.Value=10; app.Play();
            playbackTimer=app.GetSequence().Timer;
            test.verifyTrue(isvalid(playbackTimer));
            delete(app.Figure);
            test.verifyFalse(isvalid(playbackTimer));
        end

        function selectedScopeAndInvalidFilePause(test)
            test.write('file2.dat',test.sample()); test.write('file10.dat',test.swapped());
            test.write('file20.dat',sprintf('VARIABLES="X" "Y"\nZONE I=2,J=2,F=POINT\n0'));
            app=tecplot_viewer('','Visible','off','Folder',test.WorkDir);
            test.addTeardown(@()delete(app.Figure));
            app.Controls.Scope.Value='选中文件'; app.Controls.FileList.Value=[1 3];
            app.Controls.Interval.Value=.5; app.Play();
            start=tic;
            while app.GetSequence().Playing && toc(start)<10, drawnow; pause(.02); end
            test.verifyFalse(app.GetSequence().Playing);
            test.verifyEqual(app.GetSequence().Current,'file2.dat');
            test.verifyTrue(contains(app.Status.Text,'file20.dat'));
            test.verifyTrue(contains(app.Status.Text,'已暂停'));
            test.verifyEqual(app.GetSequence().Files(3).Status,'读取失败');
        end

        function missingVariableKeepsData(test)
            test.write('file2.dat',test.sample()); test.write('file10.dat',test.swapped());
            app=tecplot_viewer('','Visible','off','Folder',test.WorkDir);
            test.addTeardown(@()delete(app.Figure));
            app.SelectFile(1); before=app.GetData();
            test.write('file10.dat',sprintf('VARIABLES="X" "Y" "P"\nZONE I=2,J=2,F=POINT\n0 0 1\n1 0 1\n0 1 1\n1 1 1'));
            test.verifyFalse(app.SelectFile(2));
            test.verifyEqual(app.GetData(),before);
            test.verifyTrue(contains(app.Status.Text,'缺少已选变量'));
        end

        function unavailableZoneOrKDoesNotReset(test)
            text=test.sample(); parts=splitlines(string(text));
            rows=char(join(parts(3:end),newline));
            test.write('file2.dat',[strrep(text,'I=2,J=2','I=2,J=2,K=2'),rows]);
            test.write('file10.dat',test.swapped());
            app=tecplot_viewer('','Visible','off','Folder',test.WorkDir);
            test.addTeardown(@()delete(app.Figure));
            app.SelectFile(1); app.Controls.KSlice.Value=2; app.Render();
            before=app.GetData();
            test.verifyFalse(app.SelectFile(2));
            test.verifyEqual(app.GetData(),before);
            test.verifyTrue(contains(app.Status.Text,'Zone / K'));
            test.write('file2.dat',[text,sprintf('ZONE I=2,J=2,F=POINT\n'),rows]);
            app.Load(fullfile(test.WorkDir,'file2.dat'));
            app.SelectFile(1); app.Controls.Zone.Value=2; app.Render();
            before=app.GetData();
            test.verifyFalse(app.SelectFile(2));
            test.verifyEqual(app.GetData(),before);
        end
    end
    methods
        function path=write(test,name,text)
            path=fullfile(test.WorkDir,name); fid=fopen(path,'w','n','UTF-8');
            cleanup=onCleanup(@()fclose(fid)); fprintf(fid,'%s',text);
        end
    end
    methods(Static)
        function text=sample()
            text=sprintf('VARIABLES="X" "Y" "U" "V" "Velocity" "Flag"\nZONE I=2,J=2,F=POINT\n0 0 1 0 1 1\n1 0 1 0 1 1\n0 1 1 0 1 1\n1 1 1 0 1 1\n');
        end
        function text=swapped()
            text=sprintf('VARIABLES="Y" "X" "V" "U" "Flag" "Velocity"\nZONE I=2,J=2,F=POINT\n0 0 0 2 1 2\n0 1 0 2 1 2\n1 0 0 2 1 2\n1 1 0 2 1 2\n');
        end
        function closeApp(app)
            if isvalid(app.Figure), delete(app.Figure); end
        end
    end
end
