"""Directory discovery. A file collection does not imply a physical time series."""
from dataclasses import dataclass, field
from pathlib import Path
import os
import re


def natural_key(text):
    """Portable natural ordering, including a deterministic tie breaker."""
    parts = tuple((1, int(part)) if part.isascii() and part.isdigit() else
                  (0, part.casefold()) for part in re.split(r"([0-9]+)", str(text)))
    return parts, str(text)


@dataclass
class DatFile:
    path: Path
    relative_path: str
    status: str = "待完整验证"
    message: str = ""


@dataclass
class ScanResult:
    folder: Path
    files: list[DatFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def iter_scan_dat(folder, *, recursive=False, warnings=None):
    """Yield DAT records without reading full data; never follow directory links.

    Header checks are hints, not validity guarantees. Every file remains
    selectable and the existing strict reader is authoritative on load.
    """
    base = Path(folder).resolve(strict=True)
    if not base.is_dir():
        raise NotADirectoryError(str(base))
    pending = [base]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    linked = entry.is_symlink() or bool(getattr(entry.stat(follow_symlinks=False),
                                      "st_file_attributes", 0) & 0x400)
                    if linked:
                        continue
                    if recursive and entry.is_dir(follow_symlinks=False):
                        pending.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.casefold() == ".dat":
                        path = Path(entry.path)
                        record = DatFile(path, path.relative_to(base).as_posix())
                        try:
                            with path.open("rb") as stream:
                                head = stream.read(65536)
                            text = head.decode("utf-8-sig", errors="replace")
                            text = re.sub(r'"[^"\n]*"|#[^\n]*', ' ', text)
                            if head.startswith(b"#!TDV"):
                                record.status, record.message = "表头提示", "二进制 Tecplot 不受支持"
                            elif not (re.search(r"\bVARIABLES\s*=", text, re.I) and
                                      re.search(r"\bZONE\b", text, re.I)):
                                record.status, record.message = "表头提示", "前 64 KiB 未识别出 VARIABLES / ZONE；选择后完整验证"
                        except OSError as exc:
                            record.status, record.message = "读取失败", str(exc)
                        yield record
        except OSError as exc:
            if directory == base:
                raise
            if warnings is not None:
                warnings.append(f"{directory.relative_to(base).as_posix()}: {exc}")


def scan_dat(folder, *, recursive=False):
    """Discover .dat/.DAT in one directory, or recursively when requested."""
    result = ScanResult(Path(folder).resolve(strict=True))
    result.files = sorted(iter_scan_dat(result.folder, recursive=recursive, warnings=result.warnings),
                          key=lambda item: natural_key(item.relative_path))
    return result
