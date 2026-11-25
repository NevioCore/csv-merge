# csvmerge – merge many CSV/Excel files into one

You get the same export every week from different tools, and the columns never quite match?
`csvmerge` puts them together into one clean file.

```sh
python csvmerge.py exports/*.csv -o merged.csv --dedupe --source-column
```

```
Merged files:
  shop_export.csv: 1200 rows (encoding cp1252, delimiter ;)
  crm_export.csv: 830 rows (encoding utf-8-sig, delimiter ,)
Columns (6): Name, E-Mail, PLZ, Ort, Telefon, source_file
Rows in: 2030, rows out: 1987, duplicates removed: 43
Written: merged.csv
```

## What it does

- **Finds the right columns by name**: `E-Mail`, `email` and `EMAIL` end up in the same column; order does not matter
- **Handles German files**: Windows-1252, UTF-8 with BOM, `;` or `,` or tab
- **Keeps leading zeros** (postal codes, customer numbers)
- **Optional**: remove duplicate rows (`--dedupe`), add the source file name (`--source-column`)
- **Excel files** (`.xlsx`) with `pip install openpyxl`
- **Safe**: your input files are never changed; the output opens correctly in German Excel

Only Python 3.10+ is needed (no install for CSV files).

## Remove or flag duplicates in one file: `csvdedupe`

```sh
python csvdedupe.py products.csv -o products_clean.csv --ignore-case --removed removed.csv
python csvdedupe.py products.csv -o clean.csv --key SKU,Title      # compare only some columns
python csvdedupe.py contacts.xlsx -o flagged.csv --flag            # keep all rows, mark duplicates
```

```
Rows in: 5120, rows out: 4987
Duplicate groups: 121, rows removed: 133
Examples: A-1001 (2x), A-1007 (3x), ...
Written: products_clean.csv
```

- From each group of duplicates it keeps the row with the most filled-in cells
- Keeps row order, column order, delimiter and encoding, so the file can be imported straight back
- `--flag` adds a `duplicate_of_row` column (Excel row number) instead of deleting anything

## Tests

```sh
python -m unittest discover -s tests -t .
```

## Need something custom?

I write Python scripts that automate spreadsheet work. Contact: [Fiverr](https://www.fiverr.com/nevio_core) · [Malt](https://www.malt.de/profile/neviowaldemarniebel)

## License

MIT
