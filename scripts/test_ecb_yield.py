import unittest
from datetime import date,timedelta
from refresh_ecb_yield import FIELDS,KEY,NOTICE,SOURCE,URL,parse,validate

def sample():
    fields=[*FIELDS,"TIME_PERIOD","OBS_VALUE"]
    lines=[",".join(fields)]
    d=date(2026,9,25)
    idx=0
    while d<=date(2026,10,29):
        if d.weekday()<5:
            lines.append(",".join([*FIELDS.values(),d.isoformat(),f"{3+idx/100:.6f}"]))
            idx+=1
        d+=timedelta(days=1)
    return ("\n".join(lines)+"\n").encode()

class ECBYieldCurveTests(unittest.TestCase):
    def test_traced_reference_is_not_security_quote_or_dcf_assumption(self):
        doc=parse(sample(),"2026-10-31T15:00:00Z",today=date(2026,10,31))
        self.assertEqual(doc["series"],KEY)
        self.assertEqual(doc["source_url"],URL)
        self.assertEqual(doc["source"],SOURCE)
        self.assertIn("Not a security quote",NOTICE)
        self.assertEqual(doc["latest_date"],"2026-10-29")
        self.assertEqual(doc["count"],25)
        self.assertTrue(validate(doc,today=date(2026,10,31)))

    def test_yield_instrument_and_calendar_fail_closed(self):
        body=sample().decode()
        for broken in [
            body.replace("G_N_A","G_N_C",1),
            body.replace("3.000000",""),
            body.replace("2026-10-29","2026-10-30"),
            body.replace("2026-10-29","2027-10-29"),
            body.replace("3.000000","55.000000"),
        ]:
            with self.subTest(broken=broken[:70]):
                with self.assertRaises((ValueError,KeyError)):
                    parse(broken.encode(),"2026-10-31T15:00:00Z",today=date(2026,10,31))

    def test_macro_data_rejects_stale_or_untrusted_provenance(self):
        doc=parse(sample(),"2026-10-31T15:00:00Z",today=date(2026,10,31))
        doc["source_url"]="https://untrusted.example/macro"
        with self.assertRaises(ValueError):validate(doc,today=date(2026,10,31))
        with self.assertRaises(ValueError):
            parse(sample(),"2026-11-30T15:00:00Z",today=date(2026,11,30))

if __name__=="__main__":unittest.main()
