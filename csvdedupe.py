#!/usr/bin/env python3
"""Remove (or flag) duplicate rows in one CSV/Excel file.

- Two rows are duplicates when all compared columns match after trimming spaces
  (optionally ignoring upper/lower case)
- From each group of duplicates, the row with the most filled-in cells is kept
  (on a tie, the first one)
- Keeps the original row order, column order, delimiter and encoding, so the
  result can be imported straight back
- Can flag duplicates in an extra column instead of deleting them
- Never changes the input file; prints a short report

Usage:
    python csvdedupe.py products.csv -o products_clean.csv
    python csvdedupe.py products.csv -o clean.csv --ignore-case --removed removed.csv
    python csvdedupe.py products.csv -o clean.csv --key SKU,Title
    python csvdedupe.py contacts.xlsx -o flagged.csv --flag
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

from csvmerge import normalize_header, read_table


@dataclass
class DedupeReport:
    rows_in: int = 0
    rows_out: int = 0
    groups: int = 0
    removed: int = 0
    examples: list[str] = field(default_factory=list)

    def text(self) -> str:
        lines = [
            f"Rows in: {self.rows_in}, rows out: {self.rows_out}",
            f"Duplicate groups: {self.groups}, rows {'flagged' if self.rows_in == self.rows_out else 'removed'}: {self.removed}",
        ]
        if self.examples:
            lines.append("Examples: " + ", ".join(self.examples))
        return "\n".join(lines)


def _filled(row: list[str]) -> int:
    return sum(1 for cell in row if cell.strip())


def dedupe(
    columns: list[str],
    rows: list[list[str]],
    key: list[str] | None = None,
    ignore_case: bool = False,
    flag: bool = False,
) -> tuple[list[str], list[list[str]], list[list[str]], DedupeReport]:
    """Return (columns, kept_rows, removed_rows, report)."""
    width = len(columns)
    rows = [(r + [""] * width)[:width] for r in rows]
    if key:
        lookup = {normalize_header(c): i for i, c in enumerate(columns)}
        missing = [k for k in key if normalize_header(k) not in lookup]
        if missing:
            raise ValueError(f"column(s) not found: {', '.join(missing)}")
        idx = [lookup[normalize_header(k)] for k in key]
    else:
        idx = list(range(width))

    def make_key(row: list[str]) -> tuple[str, ...]:
        vals = (row[i].strip() for i in idx)
        return tuple(v.casefold() for v in vals) if ignore_case else tuple(vals)

    groups: dict[tuple[str, ...], list[int]] = {}
    for n, row in enumerate(rows):
        groups.setdefault(make_key(row), []).append(n)

    report = DedupeReport(rows_in=len(rows))
    best_of: dict[int, int] = {}  # row number -> row number that is kept for its group
    for members in groups.values():
        best = max(members, key=lambda n: (_filled(rows[n]), -n))
        for n in members:
            best_of[n] = best
        if len(members) > 1:
            report.groups += 1
            report.removed += len(members) - 1
            if len(report.examples) < 10:
                label = rows[best][idx[0]].strip() or f"row {best + 2}"
                report.examples.append(f"{label} ({len(members)}x)")

    kept: list[list[str]] = []
    removed: list[list[str]] = []
    if flag:
        columns = columns + ["duplicate_of_row"]
        for n, row in enumerate(rows):
            mark = "" if best_of[n] == n else str(best_of[n] + 2)  # +2: header + 1-based like Excel
            kept.append(row + [mark])
    else:
        for n, row in enumerate(rows):
            (kept if best_of[n] == n else removed).append(row)
    report.rows_out = len(kept)
    return columns, kept, removed, report


def write_csv(path: Path, columns: list[str], rows: list[list[str]], encoding: str, delimiter: str) -> None:
    if encoding not in ("utf-8-sig", "cp1252"):
        encoding = "utf-8-sig"
    if delimiter not in (",", ";", "\t", "|"):
        delimiter = ";"
    with path.open("w", newline="", encoding=encoding, errors="strict") as fh:
        writer = csv.writer(fh, delimiter=delimiter)
        writer.writerow(columns)
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Remove or flag duplicate rows in a CSV/Excel file.")
    p.add_argument("file", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--key", help="compare only these columns, comma separated (default: all)")
    p.add_argument("--ignore-case", action="store_true", help="treat 'ABC' and 'abc' as equal")
    p.add_argument("--flag", action="store_true", help="keep all rows, add a duplicate_of_row column")
    p.add_argument("--removed", type=Path, help="also write the removed rows to this file")
    args = p.parse_args(argv)

    if not args.file.exists():
        p.error(f"file not found: {args.file}")
    if args.output.resolve() == args.file.resolve():
        p.error("output must be a different file than the input")

    columns, rows, enc, delim = read_table(args.file)
    if not columns:
        p.error("the file is empty")
    key = [k.strip() for k in args.key.split(",")] if args.key else None
    try:
        columns_out, kept, removed, report = dedupe(columns, rows, key, args.ignore_case, args.flag)
    except ValueError as err:
        p.error(str(err))

    try:
        write_csv(args.output, columns_out, kept, enc, delim)
        if args.removed and removed:
            write_csv(args.removed, columns, removed, enc, delim)
    except UnicodeEncodeError:
        write_csv(args.output, columns_out, kept, "utf-8-sig", delim)
        if args.removed and removed:
            write_csv(args.removed, columns, removed, "utf-8-sig", delim)
    print(report.text())
    print(f"Written: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
