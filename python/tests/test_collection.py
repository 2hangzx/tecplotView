from pathlib import Path

import pytest

from tecplot_viewer import scan_dat
from tecplot_viewer.scan_dat import DatFile
from tecplot_viewer.sequence import FileSequence


def test_scan_defaults_recursive_headers_and_natural_order(tmp_path):
    header = 'VARIABLES="X" "Y"\nZONE I=2,J=2,F=POINT\n'
    for name in ("file_10.DAT", "file_2.dat", "file_01.dat"):
        (tmp_path / name).write_text(header + "0 0 1 0 0 1 1 1", encoding="utf-8")
    (tmp_path / "readme.dat").write_text("ordinary text", encoding="utf-8")
    (tmp_path / "binary.dat").write_bytes(b"#!TDV112")
    (tmp_path / "ignored.txt").write_text(header)
    nested = tmp_path / "child"
    nested.mkdir()
    (nested / "file_2.dat").write_text(header)
    result = scan_dat(tmp_path)
    assert [item.relative_path for item in result.files] == ["binary.dat", "file_01.dat", "file_2.dat", "file_10.DAT", "readme.dat"]
    assert result.files[0].status == "表头提示"
    assert result.files[1].status == "待完整验证"
    assert result.files[-1].message
    result = scan_dat(tmp_path, recursive=True)
    assert "child/file_2.dat" in [item.relative_path for item in result.files]
    assert len(result.files) == 6


def test_scan_empty_invalid_path_and_directory_link(tmp_path):
    assert scan_dat(tmp_path).files == []
    with pytest.raises(FileNotFoundError):
        scan_dat(tmp_path / "missing")
    ordinary = tmp_path / "text.txt"
    ordinary.write_text("text")
    with pytest.raises(NotADirectoryError):
        scan_dat(ordinary)
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "one.dat").write_text('VARIABLES="X"\nZONE I=1\n0')
    link = nested / "loop"
    try:
        link.symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        # Junctions do not require Windows developer-mode symlink privilege.
        import os
        if os.name != "nt":
            raise
        import subprocess
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(tmp_path)], check=True, capture_output=True)
    try:
        assert len(scan_dat(tmp_path, recursive=True).files) == 1
    finally:
        import os
        os.rmdir(link) if link.is_dir() and not link.is_symlink() else link.unlink()


def test_navigation_selection_direction_loop_and_no_time_assumption():
    records = [DatFile(Path(name), name) for name in ("file10.dat", "file2.dat", "file1.dat")]
    sequence = FileSequence(records)
    assert sequence.target().relative_path == "file1.dat"
    sequence.current = "file2.dat"
    assert sequence.target().relative_path == "file10.dat"
    assert sequence.target(reverse=True).relative_path == "file1.dat"
    assert sequence.target(-1).relative_path == "file1.dat"
    assert sequence.target(selected={"file1.dat", "file10.dat"}).relative_path == "file1.dat"
    sequence.current = "file10.dat"
    assert sequence.target() is None
    assert sequence.target(loop=True).relative_path == "file1.dat"
    assert sequence.target(selected=set()) is None
