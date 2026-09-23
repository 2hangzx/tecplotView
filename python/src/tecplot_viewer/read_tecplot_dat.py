"""Strict port of read_tecplot_dat.m for the same ordered/nodal subset."""
from pathlib import Path
import math
import re

import numpy as np

from .models import Dataset, TecplotError, Zone

NUMBER = re.compile(r"[+-]?(?:(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?|inf|nan)", re.I)
FIRST_NUMBER = re.compile(r"^[+-]?(?:\d|\.\d|NaN(?=[,\s]|$)|Inf(?=[,\s]|$))", re.I)
ASSIGNMENT = re.compile(r'([A-Za-z][A-Za-z0-9_]*)\s*=\s*("[^"\r\n]*"|\([^)]*\)|[^\s,]+)')


def _remove_comment(line: str) -> str:
    quoted = False
    for pos, char in enumerate(line):
        if char == '"' and (pos == 0 or line[pos - 1] != "\\"):
            quoted = not quoted
        elif char == "#" and not quoted:
            return line[:pos].strip()
    return line.strip()


def _preamble(text: str) -> tuple[str, tuple[str, ...]]:
    records = list(re.finditer(r"^\s*(TITLE|VARIABLES|FILETYPE)\s*=", text, re.I | re.M))
    if not records or text[:records[0].start()].strip():
        raise TecplotError("Header", "Expected TITLE / VARIABLES / FILETYPE before the first ZONE.")
    title, variables, seen = "", [], set()
    for index, record in enumerate(records):
        key = record[1].upper()
        if key in seen:
            raise TecplotError("Header", f"Duplicate {key} record.")
        seen.add(key)
        end = records[index + 1].start() if index + 1 < len(records) else len(text)
        value = text[record.end():end].strip()
        if key == "TITLE":
            match = re.fullmatch(r'"([^"\r\n]*)"\s*,?', value)
            if not match:
                raise TecplotError("Header", "TITLE must be a quoted string.")
            title = match[1]
        elif key == "FILETYPE":
            if value.replace(",", "").strip().upper() != "FULL":
                raise TecplotError("Unsupported", "Only FILETYPE=FULL is supported.")
        elif '"' in value:
            variables = re.findall(r'"([^"\r\n]+)"', value)
            residual = re.sub(r'"[^"\r\n]+"', "", value)
            if re.sub(r"[\s,]", "", residual):
                raise TecplotError("Header", "Malformed VARIABLES or unsupported global record.")
        else:
            variables = re.findall(r"[^\s,]+", value)
            if any("=" in name for name in variables):
                raise TecplotError("Header", "Unsupported record in VARIABLES.")
    if not variables:
        raise TecplotError("MissingVariables", "A nonempty VARIABLES record is required.")
    return title, tuple(variables)


def _number(value: str) -> float:
    return float(re.sub("[dD]", "E", value))


def _zone_header(header: str, nv: int, index: int) -> Zone:
    text = re.sub(r"^ZONE\s*", "", header, flags=re.I)
    pairs = ASSIGNMENT.findall(text)
    if re.sub(r"[\s,]", "", ASSIGNMENT.sub("", text)):
        raise TecplotError("Header", f"Zone {index} has an unsupported/malformed header.")
    allowed = {"T", "I", "J", "K", "F", "DATAPACKING", "ZONETYPE", "DT", "SOLUTIONTIME", "STRANDID"}
    meta = {}
    for key, value in pairs:
        key = key.upper()
        if key not in allowed:
            raise TecplotError("Unsupported", f"Zone {index}: {key} is unsupported; use ordered, nodal, unshared data.")
        if key in meta:
            raise TecplotError("Header", f"Zone {index}: duplicate {key}.")
        meta[key] = value
    if meta.get("ZONETYPE", "ORDERED").upper() != "ORDERED":
        raise TecplotError("Unsupported", "Only ZONETYPE=ORDERED is supported.")
    if "F" in meta and "DATAPACKING" in meta and meta["F"].upper() != meta["DATAPACKING"].upper():
        raise TecplotError("Header", "Conflicting F and DATAPACKING.")
    packing = meta.get("DATAPACKING", meta.get("F", "BLOCK")).upper()
    if packing not in {"POINT", "BLOCK"}:
        raise TecplotError("Unsupported", f"Unsupported packing: {packing}.")
    if not any(key in meta for key in ("I", "J", "K")):
        raise TecplotError("Dimensions", "Explicit I/J/K dimensions are required.")
    try:
        dimensions = [_number(meta.get(key, "1")) for key in ("I", "J", "K")]
        if any(not math.isfinite(v) or v < 1 or not v.is_integer() for v in dimensions):
            raise ValueError
        dims = tuple(map(int, dimensions))
        if math.prod(dims) * nv > 2**53:
            raise ValueError
    except ValueError as exc:
        raise TecplotError("Dimensions", "I/J/K must be positive, finite integers of supported size.") from exc
    if "DT" in meta:
        value = meta["DT"]
        types = re.split(r"[\s,]+", value[1:-1].strip().upper())
        supported = {"DOUBLE", "SINGLE", "LONGINT", "SHORTINT", "BYTE", "BIT"}
        if not (value.startswith("(") and value.endswith(")")) or len(types) != nv or not set(types) <= supported:
            raise TecplotError("Header", "DT must specify one supported type per variable.")
    time = float("nan")
    strand = None
    try:
        if "SOLUTIONTIME" in meta:
            time = _number(meta["SOLUTIONTIME"])
            if not math.isfinite(time):
                raise ValueError
        if "STRANDID" in meta:
            value = _number(meta["STRANDID"])
            if not math.isfinite(value) or value < 0 or not value.is_integer():
                raise ValueError
            strand = int(value)
    except ValueError as exc:
        raise TecplotError("Header", "Invalid SOLUTIONTIME or STRANDID.") from exc
    return Zone(meta.get("T", f"Zone {index}").strip('"'), *dims, packing,
                np.empty((0, nv)), time, strand, header)


def read_tecplot_dat(filename: str | Path, *, encoding: str = "utf-8-sig") -> Dataset:
    """Read ASCII POINT/BLOCK, multizone, explicit I/J/K, nodal data.

    Preserves original variable names and node order. Unsupported extensions
    and every malformed/extra/truncated numeric token raise TecplotError.
    """
    path = Path(filename)
    content = path.read_bytes()
    if content.startswith(b"#!TDV") or b"\0" in content:
        raise TecplotError("BinaryFile", "Use a Tecplot ASCII export, not binary PLT/SZPLT.")
    try:
        raw = content.decode(encoding).lstrip("\ufeff")
    except UnicodeDecodeError as exc:
        raise TecplotError("Encoding", f"Cannot decode {encoding}; specify the correct encoding for a text file.") from exc
    lines = [_remove_comment(line) for line in raw.splitlines()]
    starts = [n for n, line in enumerate(lines) if re.match(r"^ZONE(?=\s|$)", line, re.I)]
    if not starts:
        raise TecplotError("MissingZone", "No ZONE record was found.")
    title, variables = _preamble("\n".join(lines[:starts[0]]))
    zones = []
    for index, first in enumerate(starts):
        last = starts[index + 1] if index + 1 < len(starts) else len(lines)
        data_start = next((n for n in range(first + 1, last) if FIRST_NUMBER.match(lines[n])), None)
        if data_start is None:
            raise TecplotError("MissingData", f"Zone {index + 1} has no numeric data.")
        zone = _zone_header(" ".join(lines[first:data_start]), len(variables), index + 1)
        tokens = " ".join(lines[data_start:last]).replace(",", " ").split()
        for token in tokens:
            if not NUMBER.fullmatch(token):
                raise TecplotError("InvalidData", f"Zone {index + 1}: invalid/unsupported token {token!r}.")
        expected = zone.i * zone.j * zone.k * len(variables)
        if len(tokens) != expected:
            raise TecplotError("DataCount", f"Zone {index + 1} needs {expected} values ({zone.i} x {zone.j} x {zone.k} x {len(variables)}), has {len(tokens)}.")
        values = np.fromiter((_number(token) for token in tokens), dtype=np.float64, count=expected)
        zone.data = values.reshape((-1, len(variables)), order="C" if zone.packing == "POINT" else "F")
        zones.append(zone)
    return Dataset(title, variables, zones, path.resolve())
