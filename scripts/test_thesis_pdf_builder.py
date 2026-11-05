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

    def test_canonical_five_full_and_twenty_one_summary(self):
        records,approved=mod.verify(self.theses,self.reports)
        self.assertEqual(len(records),26)
        self.assertEqual(set(approved),{"ADBE","CAT","MSFT","META","PLTR"})
        self.assertEqual(len(records)-len(approved),20)

    def test_visual_explainers_and_semantic_source_tables(self):
        rows,approved=mod.verify(self.theses,self.reports)
        msft=next(x for x in rows if x["ticker"]=="MSFT")
        self.assertIsNotNone(mod.trajectory_chart(msft))
        self.assertIsNotNone(mod.accumulated_chart(msft))
        self.assertIsNotNone(mod.entry_chart(msft))
        blocks=mod.canonical_source_blocks(approved["MSFT"]["source_text"])
        tables=[data for kind,data in blocks if kind=="table"]
        self.assertTrue(any(len(row)==4 for table in tables for row in table))
        self.assertTrue(any(kind=="heading" and "Resumen ejecutivo" in value for kind,value in blocks if isinstance(value,str)))
        meta=mod.canonical_source_blocks(approved["META"]["source_text"])
        self.assertTrue(any(kind=="table" and any("Referencia del informe" in str(cell) for row in value for cell in row)
                            for kind,value in meta if isinstance(value,list)))
        no_values={"referencePrice":None,"bearTarget":None,"baseTarget":None,"bullTarget":None}
        self.assertIsNone(mod.trajectory_chart(no_values))
        self.assertIsNone(mod.accumulated_chart(no_values))
        self.assertIsNone(mod.entry_chart(no_values))

    def test_snapshot_structured_matrices_across_complete_issuers(self):
        records,approved=mod.verify(self.theses,self.reports)
        matrices={}
        for ticker,report in approved.items():
            tokens=mod.canonical_source_blocks(report["source_text"])
            matrices[ticker]=[value for kind,value in tokens if kind=="table"]
            self.assertTrue(matrices[ticker],ticker)
        msft=matrices["MSFT"]
        self.assertTrue(any("EV/FCF IDC implícito" in str(t[0]) for t in msft))
        self.assertTrue(any("132,63 USD" in str(t) for t in msft))
        self.assertTrue(any("106,20 USD" in str(t) for t in msft))
        adobe=matrices["ADBE"]
        self.assertTrue(any("386,86 USD" in str(t) and "866,02 USD" in str(t) for t in adobe))
        self.assertTrue(any("331,80 USD" in str(t) for t in adobe))
        pltr=matrices["PLTR"]
        self.assertTrue(any("107,59 USD" in str(t) for t in pltr))
        cat=matrices["CAT"]
        self.assertTrue(any("16,19×" in str(t) for t in cat))
        self.assertTrue(any("439 USD" in str(t) for t in cat))
        meta=matrices["META"]
        self.assertTrue(any("Referencia del informe" in str(t) for t in meta))
        msft_labels=[v for kind,v in mod.canonical_source_blocks(approved["MSFT"]["source_text"]) if kind=="heading"]
        self.assertIn("Riesgos prioritarios",msft_labels)
        self.assertIn("Indicadores a vigilar",msft_labels)
        self.assertIsNone(mod.snapshot_inline_tokens("Precio de referencia no acreditado: 300 USD"))
        self.assertIsNone(mod.snapshot_run_tokens(["No hay datos"],0))

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
