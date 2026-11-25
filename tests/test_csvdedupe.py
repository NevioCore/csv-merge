import tempfile
import unittest
from pathlib import Path

import csvdedupe

COLS = ["SKU", "Title", "Price", "Description"]


class DedupeTest(unittest.TestCase):
    def test_removes_exact_duplicates_and_keeps_order(self):
        rows = [
            ["A1", "Shirt", "10", "red"],
            ["B2", "Cap", "5", ""],
            ["A1", "Shirt", "10", "red"],
            ["C3", "Sock", "2", "x"],
        ]
        cols, kept, removed, rep = csvdedupe.dedupe(COLS, rows)
        self.assertEqual(kept, [rows[0], rows[1], rows[3]])
        self.assertEqual(removed, [rows[2]])
        self.assertEqual((rep.rows_in, rep.rows_out, rep.groups, rep.removed), (4, 3, 1, 1))

    def test_ignore_case_keeps_most_complete_row(self):
        rows = [
            ["a1", "shirt", "10", ""],
            ["A1", "Shirt", "10", ""],
        ]
        _, kept, _, _ = csvdedupe.dedupe(COLS, rows, ignore_case=True)
        self.assertEqual(kept, [rows[0]])  # tie -> first row

        rows2 = [["A1", "Shirt", "10", ""], ["A1", "Shirt", "10", "red"]]
        _, kept2, _, _ = csvdedupe.dedupe(COLS, rows2, key=["sku", "title", "price"])
        self.assertEqual(kept2, [rows2[1]])  # more filled-in cells wins

    def test_case_matters_by_default(self):
        rows = [["A1", "Shirt", "10", ""], ["a1", "shirt", "10", ""]]
        _, kept, _, _ = csvdedupe.dedupe(COLS, rows)
        self.assertEqual(len(kept), 2)

    def test_flag_mode_keeps_everything(self):
        rows = [["A1", "Shirt", "10", "red"], ["A1", "Shirt", "10", "red"]]
        cols, kept, removed, rep = csvdedupe.dedupe(COLS, rows, flag=True)
        self.assertEqual(cols[-1], "duplicate_of_row")
        self.assertEqual([r[-1] for r in kept], ["", "2"])
        self.assertEqual(removed, [])
        self.assertEqual(rep.removed, 1)

    def test_unknown_key_column(self):
        with self.assertRaises(ValueError):
            csvdedupe.dedupe(COLS, [], key=["EAN"])

    def test_cli_keeps_encoding_delimiter_and_leading_zeros(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            src = d / "in.csv"
            src.write_bytes("Nr;Name;PLZ\n001;Müller;01067\n001;Müller;01067\n002;Groß;04109\n".encode("cp1252"))
            before = src.read_bytes()
            out = d / "out.csv"
            gone = d / "removed.csv"
            self.assertEqual(csvdedupe.main([str(src), "-o", str(out), "--removed", str(gone)]), 0)
            self.assertEqual(src.read_bytes(), before)
            self.assertEqual(out.read_bytes().decode("cp1252"), "Nr;Name;PLZ\r\n001;Müller;01067\r\n002;Groß;04109\r\n")
            self.assertIn("001;Müller;01067", gone.read_bytes().decode("cp1252"))

    def test_cli_refuses_to_overwrite_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.csv"
            src.write_text("a\n1\n")
            with self.assertRaises(SystemExit):
                csvdedupe.main([str(src), "-o", str(src)])


if __name__ == "__main__":
    unittest.main()
