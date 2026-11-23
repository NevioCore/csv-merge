import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

import csvmerge


def write(path: Path, text: str, encoding="utf-8"):
    path.write_bytes(text.encode(encoding))
    return path


class MergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_matches_columns_by_name_and_keeps_leading_zeros(self):
        a = write(self.dir / "a.csv", "Name;E-Mail;PLZ\nAnna;anna@x.de;01067\n")
        b = write(self.dir / "b.csv", "plz,email,name\n04109,ben@x.de,Ben\n")
        cols, rows, rep = csvmerge.merge([a, b])
        self.assertEqual(cols, ["Name", "E-Mail", "PLZ"])
        self.assertEqual(rows, [["Anna", "anna@x.de", "01067"], ["Ben", "ben@x.de", "04109"]])
        self.assertEqual(rep.rows_in, 2)

    def test_cp1252_and_bom_and_tab(self):
        a = write(self.dir / "a.csv", "Straße;Ort\nHauptstr. 1;Köln\n", encoding="cp1252")
        b = write(self.dir / "b.tsv", "﻿Strasse\tOrt\nRingweg 2\tMünchen\n")
        cols, rows, rep = csvmerge.merge([a, b])
        self.assertEqual(cols, ["Straße", "Ort"])
        self.assertEqual(rows[1], ["Ringweg 2", "München"])
        self.assertEqual(rep.files[0][2], "cp1252")
        self.assertEqual(rep.files[1][3], "\t")

    def test_new_columns_are_added_and_missing_cells_empty(self):
        a = write(self.dir / "a.csv", "id,name\n1,A\n")
        b = write(self.dir / "b.csv", "id,phone\n2,0151\n")
        cols, rows, _ = csvmerge.merge([a, b])
        self.assertEqual(cols, ["id", "name", "phone"])
        self.assertEqual(rows, [["1", "A", ""], ["2", "", "0151"]])

    def test_dedupe_and_source_column(self):
        a = write(self.dir / "a.csv", "id,name\n1,Anna\n2,Ben\n")
        b = write(self.dir / "b.csv", "id,name\n1,ANNA\n3,Cem\n")
        cols, rows, rep = csvmerge.merge([a, b], dedupe=True, source_column=True)
        self.assertEqual(cols[-1], "source_file")
        self.assertEqual([r[1] for r in rows], ["Anna", "Ben", "Cem"])
        self.assertEqual(rep.duplicates_removed, 1)

    def test_quoted_delimiters_and_blank_lines(self):
        a = write(self.dir / "a.csv", 'name,note\n"Doe, John","said ""hi"""\n\n')
        _, rows, _ = csvmerge.merge([a])
        self.assertEqual(rows, [["Doe, John", 'said "hi"']])

    def test_cli_writes_output_and_never_touches_input(self):
        a = write(self.dir / "a.csv", "id;name\n1;Ä\n")
        before = hashlib.sha256(a.read_bytes()).hexdigest()
        out = self.dir / "out.csv"
        self.assertEqual(csvmerge.main([str(a), "-o", str(out)]), 0)
        self.assertEqual(hashlib.sha256(a.read_bytes()).hexdigest(), before)
        with out.open(encoding="utf-8-sig", newline="") as fh:
            self.assertEqual(list(csv.reader(fh, delimiter=";")), [["id", "name"], ["1", "Ä"]])

    def test_cli_refuses_to_overwrite_input(self):
        a = write(self.dir / "a.csv", "id\n1\n")
        with self.assertRaises(SystemExit):
            csvmerge.main([str(a), "-o", str(a)])

    def test_xlsx(self):
        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl not installed")
        wb = Workbook()
        wb.active.append(["Name", "PLZ"])
        wb.active.append(["Eva", "01234"])
        x = self.dir / "c.xlsx"
        wb.save(x)
        a = write(self.dir / "a.csv", "name;plz\nAnna;01067\n")
        cols, rows, _ = csvmerge.merge([a, x])
        self.assertEqual(rows[1], ["Eva", "01234"])


if __name__ == "__main__":
    unittest.main()
