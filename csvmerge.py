#!/usr/bin/env python3
"""Merge many CSV/TSV (and optionally .xlsx) files into one clean CSV.

- Detects encoding (UTF-8, UTF-8 with BOM, Windows-1252) and delimiter per file
- Matches columns by name, even if the order or spelling ("E-Mail" vs "email") differs
- Keeps leading zeros (everything is read as text)
- Optional: remove exact duplicate rows
- Never changes your input files; prints a short report

Usage:
    python csvmerge.py data/*.csv -o merged.csv
    python csvmerge.py a.csv b.xlsx -o merged.csv --dedupe --source-column
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

ENCODINGS = ("utf-8-sig", "cp1252")


@dataclass
class Report:
    files: list[tuple[str, int, str, str]] = field(default_factory=list)  # name, rows, encoding, delimiter
    columns: list[str] = field(default_factory=list)
    rows_in: int = 0
    rows_out: int = 0
    duplicates_removed: int = 0

    def text(self) -> str:
        lines = ["Merged files:"]
        for name, rows, enc, delim in self.files:
            shown = {"\t": "TAB", ";": ";", ",": ","}.get(delim, delim)
            lines.append(f"  {name}: {rows} rows (encoding {enc}, delimiter {shown})")
        lines.append(f"Columns ({len(self.columns)}): {', '.join(self.columns)}")
        lines.append(f"Rows in: {self.rows_in}, rows out: {self.rows_out}, duplicates removed: {self.duplicates_removed}")
        return "\n".join(lines)


def normalize_header(name: str) -> str:
    """'E-Mail ' -> 'email', 'Straße' -> 'strasse'. Used only for matching columns."""
    text = unicodedata.normalize("NFKD", name.replace("ß", "ss")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def decode(data: bytes) -> tuple[str, str]:
    for enc in ENCODINGS:
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise ValueError("unknown encoding")  # cp1252 decodes almost anything, so this is rare


def sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {d: sample.split("\n", 1)[0].count(d) for d in ",;\t|"}
        return max(counts, key=counts.get) if max(counts.values()) else ","


def read_table(path: Path) -> tuple[list[str], list[list[str]], str, str]:
    if path.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as err:
            raise SystemExit("Reading .xlsx needs openpyxl: pip install openpyxl") from err
        ws = load_workbook(path, read_only=True, data_only=True).active
        rows = [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
        enc, delim = "xlsx", "-"
    else:
        text, enc = decode(path.read_bytes())
        delim = sniff_delimiter(text[:4096])
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        return [], [], enc, delim
    return [h.strip() for h in rows[0]], rows[1:], enc, delim


def merge(paths: list[Path], dedupe: bool = False, source_column: bool = False) -> tuple[list[str], list[list[str]], Report]:
    report = Report()
    columns: list[str] = []
    key_to_index: dict[str, int] = {}
    merged: list[dict[int, str]] = []

    for path in paths:
        header, rows, enc, delim = read_table(path)
        report.files.append((path.name, len(rows), enc, delim))
        mapping = []
        for h in header:
            key = normalize_header(h) or f"column{len(columns) + 1}"
            if key not in key_to_index:
                key_to_index[key] = len(columns)
                columns.append(h or f"column{len(columns) + 1}")
            mapping.append(key_to_index[key])
        for row in rows:
            report.rows_in += 1
            record = {mapping[i]: v.strip() for i, v in enumerate(row) if i < len(mapping)}
            if source_column:
                record[-1] = path.name
            merged.append(record)

    out_columns = columns + (["source_file"] if source_column else [])
    order = list(range(len(columns))) + ([-1] if source_column else [])
    out_rows = [[rec.get(i, "") for i in order] for rec in merged]

    if dedupe:
        seen, unique = set(), []
        compare = slice(0, len(columns))  # ignore source_file when comparing
        for row in out_rows:
            key = tuple(c.casefold() for c in row[compare])
            if key in seen:
                report.duplicates_removed += 1
                continue
            seen.add(key)
            unique.append(row)
        out_rows = unique

    report.columns = out_columns
    report.rows_out = len(out_rows)
    return out_columns, out_rows, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge CSV/TSV/XLSX files into one CSV.")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--delimiter", default=";", help="output delimiter (default ';' for German Excel)")
    parser.add_argument("--dedupe", action="store_true", help="remove exact duplicate rows (case-insensitive)")
    parser.add_argument("--source-column", action="store_true", help="add a column with the source file name")
    args = parser.parse_args(argv)

    if args.output.resolve() in {p.resolve() for p in args.files}:
        parser.error("output must not be one of the input files")
    missing = [str(p) for p in args.files if not p.is_file()]
    if missing:
        parser.error("file not found: " + ", ".join(missing))

    columns, rows, report = merge(args.files, dedupe=args.dedupe, source_column=args.source_column)
    with args.output.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM so Excel shows umlauts
        writer = csv.writer(fh, delimiter=args.delimiter)
        writer.writerow(columns)
        writer.writerows(rows)
    print(report.text())
    print(f"Written: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
