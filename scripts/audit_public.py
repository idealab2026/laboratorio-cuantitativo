#!/usr/bin/env python3
"""Fail-closed allowlisted public build gate for an institutional static research site."""
from pathlib import Path
from html.parser import HTMLParser
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
RELEASE = {"index.html", "research.html", "styles.css", "favicon.svg", "logo.svg", "src/site.mjs", "src/metrics.mjs", "src/learning.mjs", "src/learning-view.mjs", "src/paper-methods.mjs", "src/paper-ledger.mjs", "src/competition-roster.mjs", "src/paper-feed.mjs", "data/demo.json", "data/fx-forecast-ledger.json", "data/sec-filings.json", "data/competition-roster.json", "data/institutional-paper-feed.json"}
REPOSITORY = RELEASE | {"README.md", "docs/SCIENTIFIC_PARITY.md", "scripts/audit_public.py", "scripts/refresh_ecb.py", "scripts/test_ecb.py", "scripts/advance_fx.py", "scripts/test_advance_fx.py", "scripts/refresh_sec.py", "scripts/test_sec.py", "scripts/refresh_ecb_yield.py", "scripts/test_ecb_yield.py", "scripts/yahoo_source.py", "scripts/test_yahoo_source.py", "data/universe-xnys.json", "scripts/requirements-yahoo.txt", "data/public-paper-book.json", "scripts/public_market_runner.py", "scripts/test_public_market_runner.py", "scripts/classic_503.py", "scripts/test_classic_503.py", "scripts/classic_503_book.py", "scripts/test_classic_503_book.py", "scripts/monthly_selection.py", "scripts/test_monthly_selection.py", "scripts/monthly_paper.py", "scripts/test_monthly_paper.py", "data/monthly-paper-book.json", "data/classic-503-book.json", ".github/workflows/public-market.yml", "scripts/paper_feed.py", "scripts/test_paper_feed.py", "tests/metrics.test.mjs", "tests/learning.test.mjs", "tests/paper-methods.test.mjs", "tests/paper-ledger.test.mjs", "tests/competition-roster.test.mjs", "tests/paper-feed.test.mjs", ".github/workflows/pages.yml", ".github/workflows/fx-ledger.yml", ".github/workflows/sec-filings.yml"}
issues = []
files = {str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts}
if unknown := sorted(files - REPOSITORY):
    issues.append("Unapproved additional files: " + str(len(unknown)))
if missing := sorted(REPOSITORY - files):
    issues.append("Missing required files: " + str(len(missing)))

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.references=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ("a","link","img","script"):
            u=a.get("href") or a.get("src")
            if u: self.references.append(u)
for page in ("index.html", "research.html"):
 if not (ROOT/page).exists(): continue
 links=Links()
 links.feed((ROOT/page).read_text(encoding="utf8"))
 for url in links.references:
        if url.startswith("#"): continue
        if url.startswith("https://"):
            if not (url.startswith("https://idealab2026.github.io/") or url.startswith("https://github.com/idealab2026/") or url == "https://static.cloudflareinsights.com/beacon.min.js"):
                issues.append("Non-institutional external link")
        elif url.startswith("./"):
            if url[2:] not in RELEASE: issues.append("Dependency not on release allowlist")
        else: issues.append("Unexpected link or source type")
for path in sorted(files):
    if path not in REPOSITORY: continue
    source=(ROOT/path).read_text(encoding="utf8")
    if path in RELEASE or path == "README.md" or path.startswith("docs/"):
        if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",source):
            issues.append("Email address found in public content")
    if re.search(r"-----BEGIN [^-]+PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{30,}",source):
        issues.append("Credential-like content")
    if re.search(r"https?://(?:localhost|127\.0\.0\.1|[^\s/]*\.workers\.dev)",source,re.I):
        issues.append("Unexpected local or backend reference")
sample=ROOT/"data/demo.json"
if sample.exists():
    try:
        if json.loads(sample.read_text(encoding="utf8")).get("meta",{}).get("data_class")!="synthetic":
            issues.append("Dataset not admitted for a public synthetic demonstration")
    except (OSError,ValueError):
        issues.append("Invalid dataset")
if issues:
    print("PUBLIC RELEASE REJECTED:",*sorted(set(issues)),sep="\n- ")
    sys.exit(1)
print("OK: allowlist, source scanning, institutional links and synthetic demonstration")
