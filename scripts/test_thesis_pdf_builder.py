"""Quality gate for all publicly reproducible corporate thesis PDFs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("build_thesis_pdfs",ROOT/"scripts/build_thesis_pdfs.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ThesisPDFTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.theses=json.loads((ROOT/"data/public-theses.json").read_text("utf8"))
        cls.reports=json.loads((ROOT/"data/thesis-reports.json").read_text("utf8"))

    def test_canonical_five_full_and_twenty_summary(self):
        records,approved=mod.verify(self.theses,self.reports)
        self.assertEqual(len(records),25)
        self.assertEqual(set(approved),{"ADBE","CAT","MSFT","META","PLTR"})
        self.assertEqual(len(records)-len(approved),20)

    def test_private_workpaper_links_are_rejected(self):
        broken={"schema":self.reports["schema"],"reports":[{
            "ticker":"MSFT","publication_gate":"approved",
            "source_text":"a"*600+" https://docs.google.com/internal"}]}
        with self.assertRaises(ValueError):
            mod.verify(self.theses,broken)

    def test_reportlab_generates_valid_pdf(self):
        records,approved=mod.verify(self.theses,self.reports)
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/"MSFT.pdf"
            sample=next(x for x in records if x["ticker"]=="MSFT")
            mod.report_pdf(sample,approved["MSFT"],output)
            self.assertTrue(output.read_bytes().startswith(b"%PDF"))
            self.assertGreater(output.stat().st_size,8000)

if __name__=="__main__":
    unittest.main()
