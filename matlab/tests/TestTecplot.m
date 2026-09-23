classdef TestTecplot < matlab.unittest.TestCase
    properties
        WorkDir
    end
    methods (TestMethodSetup)
        function setup(test)
            test.WorkDir = tempname;
            mkdir(test.WorkDir);
            % Only remove this unique test-owned temporary directory.
            test.addTeardown(@()rmdir(test.WorkDir, 's'));
        end
    end
    methods (Test)
        function screenshotSchemaAndOrientation(test)
            file = make_demo_dat(fullfile(test.WorkDir,'piv.dat'));
            d = read_tecplot_dat(file);
            test.verifyEqual(size(d.Zones.Data), [12087,9]);
            test.verifyEqual([d.Zones.I,d.Zones.J,d.Zones.K], [153,79,1]);
            test.verifyEqual(d.Variables{4},'U(m/s)');
            x = tecplot_grid(d,'X'); y = tecplot_grid(d,'Y');
            test.verifyEqual(size(x),[79,153]);
            test.verifyEqual(x(1,:),253:4:861);
            test.verifyEqual(y(:,1),(512:4:824).');
            test.verifyEqual(d.Zones.Data(154,1:2),[253,516]);
            test.verifyLessThan(max(abs(d.Zones.Data(:,7)-hypot(d.Zones.Data(:,4),d.Zones.Data(:,5)))),1e-9);
        end
        function blockMultizoneAndKSlices(test)
            header = sprintf('TITLE="two zones"\nVARIABLES="X" "Y" "U"\n');
            first = sprintf('ZONE T="first", I=2,J=2,K=2,DATAPACKING=BLOCK,ZONETYPE=ORDERED\nSOLUTIONTIME=1D-3,STRANDID=1\n');
            a = [(1:8).',(11:18).',(21:28).'];
            second = sprintf('\nZONE T="second", I=2,J=2,F=POINT\n');
            b = [1 10 100;2 10 200;1 20 300;2 20 400];
            file = test.write('multi.dat',[header,first,sprintf('%g ',a(:)),second,sprintf('%g ',b.')]);
            d = read_tecplot_dat(file);
            test.verifyEqual(numel(d.Zones),2);
            test.verifyEqual(d.Zones(1).Data,a);
            test.verifyEqual(d.Zones(2).Data,b);
            test.verifyEqual(d.Zones(1).SolutionTime,.001);
            g = tecplot_grid(d,1,1);
            test.verifyEqual(g(:,:,2),[5,6;7,8]);
        end
        function commentsCommasBomAndMultilineVariables(test)
            txt = sprintf('TITLE="keep # in title"\nVARIABLES="X(mm)",\n"Y(mm)" "U(m/s)"\n# comment\nZONE I=2,J=1,F=POINT\n0, 1, 2D-3 # comment\n4\t5\t-6d+1\n');
            file = test.write('flex.dat',[char(65279),txt]);
            d = read_tecplot_dat(file);
            test.verifyEqual(d.Title,'keep # in title');
            test.verifyEqual(d.Zones.Data,[0 1 .002;4 5 -60]);
        end
        function rejectTruncationExtraValuesAndText(test)
            head = sprintf('VARIABLES="X" "Y"\nZONE I=2,F=POINT\n');
            test.verifyError(@()read_tecplot_dat(test.write('short.dat',[head,'1 2 3'])), 'tecplot:DataCount');
            test.verifyError(@()read_tecplot_dat(test.write('long.dat',[head,'1 2 3 4 5'])), 'tecplot:DataCount');
            test.verifyError(@()read_tecplot_dat(test.write('bad.dat',[head,'1 2 3 4 BAD'])), 'tecplot:InvalidData');
            test.verifyError(@()read_tecplot_dat(test.write('badexp.dat',[head,'1e 2 3 4'])), 'tecplot:InvalidData');
        end
        function nonfiniteValuesAndMalformedMetadata(test)
            file = test.write('nan.dat',sprintf('VARIABLES="X" "Y"\nZONE I=2,F=POINT\nNaN 1 Inf -2\n'));
            d = read_tecplot_dat(file);
            test.verifyTrue(isnan(d.Zones.Data(1,1)));
            test.verifyEqual(d.Zones.Data(2,1),Inf);
            file = test.write('dims.dat',sprintf('VARIABLES="X"\nZONE I=2.5,F=POINT\n1 2\n'));
            test.verifyError(@()read_tecplot_dat(file),'tecplot:Dimensions');
            file = test.write('dt.dat',sprintf('VARIABLES="X" "Y"\nZONE I=2,F=POINT,DT=(DOUBLE)\n1 2 3 4\n'));
            test.verifyError(@()read_tecplot_dat(file),'tecplot:Header');
        end
        function rejectUnsupportedLayouts(test)
            head = sprintf('VARIABLES="X" "Y"\n');
            variants = {'ZONE N=2,E=1,F=FEPOINT', 'ZONE I=2,F=POINT,VARLOCATION=([2]=CELLCENTERED)', ...
                'ZONE I=2,F=POINT,VARSHARELIST=([1]=1)', 'ZONE I=2,F=POINT,PASSIVEVARLIST=[2]', ...
                'ZONE I=2,F=POINT,ZONETYPE=FETRIANGLE'};
            for k = 1:numel(variants)
                file = test.write(sprintf('unsupported%d.dat',k),sprintf('%s%s\n1 2 3 4',head,variants{k}));
                test.verifyError(@()read_tecplot_dat(file),'tecplot:Unsupported');
            end
            file = test.write('binary.dat','#!TDV112 binary');
            test.verifyError(@()read_tecplot_dat(file),'tecplot:BinaryFile');
        end
        function variableResolution(test)
            vars = {'X(mm)','U(m/s)','U(cm/s)'};
            test.verifyEqual(tecplot_variable(vars,'x'),1);
            test.verifyEqual(tecplot_variable(vars,'U(m/s)'),2);
            test.verifyError(@()tecplot_variable(vars,'U'),'tecplot:Variable');
            test.verifyEmpty(tecplot_variable(vars,'W',false));
        end
        function renderingModesAndMasking(test)
            file = make_demo_dat(fullfile(test.WorkDir,'render.dat'));
            d = read_tecplot_dat(file);
            f = figure('Visible','off'); test.addTeardown(@()close(f));
            ax = axes(f);
            modes = {'heatmap','contour','quiver','overlay','streamlines','surface','mesh'};
            for k = 1:numel(modes)
                [~,~,info] = tecplot_plot(d,'Axes',ax,'Mode',modes{k},'ValidFlagValues',1,'Stride',8);
                drawnow;
                test.verifyNotEmpty(ax.Children);
                test.verifyEqual(info.FlagMask,tecplot_grid(d,'Flag')==1);
                if ~isempty(info.Scalar)
                    test.verifyTrue(all(isnan(info.Scalar(~info.FlagMask))));
                end
            end
            [~,~,info] = tecplot_plot(d,'Axes',ax,'Variable','Vorticity','CLim',[-1 1],'ReverseY',true);
            test.verifyTrue(all(info.FlagMask(:))); % Flags preserved by default.
            test.verifyEqual(ax.YDir,'reverse');
            test.verifyEqual(ax.CLim,[-1 1]);
            test.verifyEqual(info.Scalar,tecplot_grid(d,'Vorticity'));
        end
        function descendingAxesAndCurvedStreamGrid(test)
            file = make_demo_dat(fullfile(test.WorkDir,'stream.dat'));
            d = read_tecplot_dat(file);
            d.Zones.Data(:,1) = -d.Zones.Data(:,1);
            d.Zones.Data(:,2) = -d.Zones.Data(:,2);
            f = figure('Visible','off'); test.addTeardown(@()close(f)); ax=axes(f);
            tecplot_plot(d,'Axes',ax,'Mode','streamlines','Stride',15);
            test.verifyNotEmpty(findobj(ax,'Type','line'));
            d.Zones.Data(2,2) = d.Zones.Data(2,2) + 1;
            test.verifyError(@()tecplot_plot(d,'Axes',ax,'Mode','streamlines'),'tecplot:StreamGrid');
        end
        function noVelocityForScalarAndConstantContour(test)
            file = test.write('scalar.dat',sprintf('VARIABLES="X" "Y" "P"\nZONE I=2,J=2,F=POINT\n0 0 7\n1 0 7\n0 1 7\n1 1 7\n'));
            f = figure('Visible','off'); test.addTeardown(@()close(f)); ax=axes(f);
            [~,~,info] = tecplot_plot(file,'Axes',ax,'Mode','contour','Variable','P');
            test.verifyEqual(info.Scalar,7*ones(2));
            test.verifyNotEmpty(findobj(ax,'Type','surface'));
            test.verifyError(@()tecplot_plot(file,'Axes',ax,'Mode','quiver'),'tecplot:Variable');
        end
        function exportAndGuiCallbacks(test)
            file = make_demo_dat(fullfile(test.WorkDir,'gui.dat'));
            out = fullfile(test.WorkDir,'export.png');
            tecplot_cli(file,out,'Mode','overlay','Variable','Velocity');
            test.verifyTrue(isfile(out));
            imageInfo = imfinfo(out);
            test.verifyGreaterThan(imageInfo.Width,500);
            app = tecplot_viewer(file,'Visible','off');
            test.addTeardown(@()delete(app.Figure));
            test.verifyNotEmpty(app.Axes.Children);
            app.Controls.Mode.Value = 'contour';
            app.Controls.Variable.Value = 8;
            app.Controls.Flags.Value = '1';
            app.Controls.AutoCLim.Value = false;
            app.Controls.CLimMin.Value = -1;
            app.Controls.CLimMax.Value = 1;
            app.Render();
            test.verifyEqual(app.Axes.CLim,[-1 1]);
            current = app.GetData();
            test.verifyEqual(numel(current.Variables),9);
            scalarFile = test.write('scalar_gui.dat',sprintf('VARIABLES="X" "Y" "P"\nZONE I=2,J=2,F=POINT\n0 0 7\n1 0 7\n0 1 7\n1 1 7\n'));
            app.Load(scalarFile);
            current = app.GetData();
            test.verifyEqual(numel(current.Variables),3);
            test.verifyEqual(app.Controls.Mode.Value,'heatmap');
            test.verifyEqual(app.Controls.Variable.Value,3);
        end
        function customColorbarLimitsAndAutomaticReset(test)
            file = make_demo_dat(fullfile(test.WorkDir,'limits.dat'));
            app = tecplot_viewer(file,'Visible','off');
            test.addTeardown(@()delete(app.Figure));
            c = app.Controls;
            test.verifyEqual([c.CLimMin.Value,c.CLimMax.Value],app.Axes.CLim);
            test.verifyEqual(char(c.CLimMin.Enable),'off');
            % Exercise the actual callbacks, including decimal/negative limits.
            c.AutoCLim.Value = false;
            c.AutoCLim.ValueChangedFcn(c.AutoCLim,[]);
            test.verifyEqual(char(c.CLimMin.Enable),'on');
            c.CLimMin.Value = -0.02;
            c.CLimMin.ValueChangedFcn(c.CLimMin,[]);
            c.CLimMax.Value = 0.06;
            c.CLimMax.ValueChangedFcn(c.CLimMax,[]);
            test.verifyEqual(app.Axes.CLim,[-0.02,0.06]);
            cb = findall(app.Figure,'Type','colorbar');
            test.verifyEqual(cb.Limits,[-0.02,0.06]);
            c.Variable.Value = 8;
            c.Colormap.Value = 'jet';
            c.Colormap.ValueChangedFcn(c.Colormap,[]);
            test.verifyEqual(app.Axes.CLim,[-0.02,0.06]);
            % An invalid range must leave the previous rendered limits intact.
            c.CLimMin.Value = 0.06;
            test.verifyError(@()app.Render(),'tecplot:ColorLimits');
            test.verifyEqual(app.Axes.CLim,[-0.02,0.06]);
            c.CLimMin.Value = 1;
            c.CLimMin.ValueChangedFcn(c.CLimMin,[]);
            test.verifyTrue(contains(app.Status.Text,'下限必须小于上限'));
            c.CLimMin.Value = -0.02;
            app.Render();
            c.Mode.Value = 'quiver'; app.Render();
            test.verifyEqual(char(c.CLimMin.Enable),'off');
            c.Mode.Value = 'contour'; app.Render();
            test.verifyEqual(app.Axes.CLim,[-0.02,0.06]);
            c.AutoCLim.Value = true;
            c.AutoCLim.ValueChangedFcn(c.AutoCLim,[]);
            test.verifyLessThan(app.Axes.CLim(1),-0.1);
            test.verifyEqual([c.CLimMin.Value,c.CLimMax.Value],app.Axes.CLim);
            test.verifyEqual(char(c.CLimMax.Enable),'off');
        end
    end
    methods
        function file = write(test,name,text)
            file = fullfile(test.WorkDir,name);
            fid = fopen(file,'w','n','UTF-8');
            cleanup = onCleanup(@()fclose(fid));
            fprintf(fid,'%s',text);
        end
    end
end
