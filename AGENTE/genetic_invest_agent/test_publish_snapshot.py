import subprocess,sys,unittest
from pathlib import Path
class PublicationTransport(unittest.TestCase):
 def test_check_is_read_only_and_keeps_custodied_journal_bytes(self):
  import hashlib
  root=Path(__file__).resolve().parent
  paths=list((root/'registro_historico').glob('*.json'))
  before={p:hashlib.sha256(p.read_bytes()).digest() for p in paths}
  subprocess.run([sys.executable,str(root/'publish_snapshot.py'),'--check-only'],check=True)
  self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).digest() for p in paths})
