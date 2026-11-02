"""Validate and publish the existing paper dashboard through institutional Git only."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--check-only',action='store_true');a=p.parse_args()
 subprocess.run([sys.executable,str(Path(__file__).with_name('audit_publication.py'))],cwd=ROOT,check=True)
 if a.check_only:
  print('Institutional Git publication validated; no network or journal mutation')
  return
 subprocess.run([sys.executable,'strategy_comparison/report.py','--registry','strategy_comparison/registry.json','--paper-config','paper_demo/config.json','--paper-state','paper_state/state.json','--tfm-config','tfm_shadow/config.json','--tfm-state','tfm_state/ledger.json','--weekly-ml-config','weekly_ml/config.json','--weekly-ml-state','weekly_ml_state/ledger.json','--tfg-config','tfg_ahp/config.json','--tfg-state','tfg_state/ledger.json','--output','strategy_state'],cwd=ROOT,check=True)
 subprocess.run([sys.executable,'strategy_comparison/publish_state.py','--message','Refresh public genetic paper summary','--path','strategy_state'],cwd=ROOT,check=True)
if __name__=='__main__':main()
