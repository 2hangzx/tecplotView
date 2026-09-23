import numpy as np
import pytest

from tecplot_viewer import (TecplotError, make_demo_dat, read_tecplot_dat,
                            tecplot_grid, tecplot_variable)


def test_matlab_sample_and_orientation(sample, demo):
    d = read_tecplot_dat(sample)
    z = d.zones[0]
    assert (z.i, z.j, z.k) == (153, 79, 1)
    assert z.data.shape == (12087, 9)
    assert d.variables[3] == "U(m/s)"
    x, y = tecplot_grid(d, "X"), tecplot_grid(d, "Y")
    assert x.shape == (79, 153, 1)
    np.testing.assert_array_equal(x[0, :, 0], np.arange(253, 862, 4))
    np.testing.assert_array_equal(y[:, 0, 0], np.arange(512, 825, 4))
    np.testing.assert_array_equal(z.data[153, :2], [253, 516])
    # MATLAB-generated .9g output vs Python's full-precision analytical field.
    np.testing.assert_allclose(z.data, demo.zones[0].data, rtol=5e-9, atol=5e-10)


def test_demo_roundtrip_and_overwrite_guard(tmp_path):
    path = make_demo_dat(tmp_path / "demo.dat")
    first = read_tecplot_dat(path)
    with pytest.raises(FileExistsError):
        make_demo_dat(path)
    make_demo_dat(path, overwrite=True)
    np.testing.assert_array_equal(first.zones[0].data, read_tecplot_dat(path).zones[0].data)


def test_multizone_block_point_k_slice(dat_file):
    a = np.column_stack([np.arange(1, 9), np.arange(11, 19), np.arange(21, 29)])
    b = np.array([[1, 10, 100], [2, 10, 200], [1, 20, 300], [2, 20, 400]])
    text = 'TITLE="two zones"\nVARIABLES="X" "Y" "U"\n'
    text += 'ZONE T="first",I=2,J=2,K=2,DATAPACKING=BLOCK,ZONETYPE=ORDERED\nSOLUTIONTIME=1D-3,STRANDID=1\n'
    text += " ".join(map(str, a.ravel(order="F")))
    text += '\nZONE T="second",I=2,J=2,F=POINT\n' + " ".join(map(str, b.ravel()))
    d = read_tecplot_dat(dat_file(text))
    assert len(d.zones) == 2
    np.testing.assert_array_equal(d.zones[0].data, a)
    np.testing.assert_array_equal(d.zones[1].data, b)
    np.testing.assert_array_equal(tecplot_grid(d, 1)[:, :, 1], [[5, 6], [7, 8]])
    assert d.zones[0].solution_time == .001
    assert d.zones[0].strand_id == 1


def test_bom_comments_commas_multiline_and_d_exponents(dat_file):
    text = '\ufeffTITLE="keep # in title"\r\nVARIABLES="X(mm)",\r\n"Y(mm)" "U(m/s)"\n# comment\nZONE I=2,J=1,F=POINT\n0,1,2D-3 # comment\n4\t5\t-6d+1\n'
    d = read_tecplot_dat(dat_file(text))
    assert d.title == "keep # in title"
    np.testing.assert_array_equal(d.zones[0].data, [[0, 1, .002], [4, 5, -60]])


@pytest.mark.parametrize("body,code", [
    ("1 2 3", "DataCount"), ("1 2 3 4 5", "DataCount"),
    ("1 2 3 BAD", "InvalidData"), ("1e 2 3 4", "InvalidData"),
    ("1 2 3 4 TRAILING", "InvalidData"), ("1 2 3 2*4", "InvalidData")])
def test_bad_numeric_records(dat_file, body, code):
    with pytest.raises(TecplotError) as exc:
        read_tecplot_dat(dat_file('VARIABLES="X" "Y"\nZONE I=2,F=POINT\n' + body))
    assert exc.value.code == code


@pytest.mark.parametrize("zone", [
    "ZONE N=2,E=1,F=FEPOINT", "ZONE I=2,F=POINT,VARLOCATION=([2]=CELLCENTERED)",
    "ZONE I=2,F=POINT,VARSHARELIST=([1]=1)", "ZONE I=2,F=POINT,PASSIVEVARLIST=[2]",
    "ZONE I=2,F=POINT,ZONETYPE=FETRIANGLE", 'ZONE I=2,F=POINT,AUXDATA NAME="value"'])
def test_reject_unsupported_layouts(dat_file, zone):
    with pytest.raises(TecplotError):
        read_tecplot_dat(dat_file(f'VARIABLES="X" "Y"\n{zone}\n1 2 3 4'))


@pytest.mark.parametrize("zone,code", [
    ("ZONE I=2.5,F=POINT", "Dimensions"), ("ZONE I=0,F=POINT", "Dimensions"),
    ("ZONE I=2,F=POINT,DT=(DOUBLE)", "Header"), ("ZONE I=2,F=POINT,DATAPACKING=BLOCK", "Header"),
    ("ZONE I=2,F=POINT,DT=(DOUBLE@ DOUBLE)", "Header"),
    ("ZONE I=2,I=2,F=POINT", "Header"), ("ZONE F=POINT", "Dimensions"),
    ("ZONE I=2,F=POINT,SOLUTIONTIME=garbage", "Header")])
def test_bad_metadata(dat_file, zone, code):
    with pytest.raises(TecplotError) as exc:
        read_tecplot_dat(dat_file(f'VARIABLES="X" "Y"\n{zone}\n1 2 3 4'))
    assert exc.value.code == code


def test_missing_records_binary_and_nan(dat_file):
    for text, code in [("#!TDV112 binary", "BinaryFile"), ("1 2 3", "MissingZone"),
                       ('TITLE="no vars"\nZONE I=1\n1', "MissingVariables"),
                       ('VARIABLES="X"\nZONE I=1\n', "MissingData")]:
        with pytest.raises(TecplotError) as exc:
            read_tecplot_dat(dat_file(text))
        assert exc.value.code == code
    d = read_tecplot_dat(dat_file('VARIABLES="X" "Y"\nZONE I=2,F=POINT\nNaN 1 Inf -2\n'))
    assert np.isnan(d.zones[0].data[0, 0])
    assert np.isinf(d.zones[0].data[1, 0])


def test_default_block_and_unquoted_names(dat_file):
    d = read_tecplot_dat(dat_file('FILETYPE=FULL\nVARIABLES=X Y\nZONE I=2\n1 2 3 4'))
    np.testing.assert_array_equal(d.zones[0].data, [[1, 3], [2, 4]])


def test_variables_and_indices(demo):
    names = ("X(mm)", "U(m/s)", "U(cm/s)")
    assert tecplot_variable(names, "x") == 0
    assert tecplot_variable(names, "U(m/s)") == 1
    assert tecplot_variable(names, 3) == 2
    assert tecplot_variable(names, "W", False) is None
    for selection in ("U", "missing", 0, 4, True, 1.2):
        with pytest.raises(TecplotError):
            tecplot_variable(names, selection)
    with pytest.raises(TecplotError):
        tecplot_grid(demo, "U", zone=0)
