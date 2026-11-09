#!/usr/bin/env python3
"""Fail-closed allowlisted public build gate for an institutional static research site."""
from pathlib import Path
from html.parser import HTMLParser
import json
import re
import sys
sys.dont_write_bytecode = True
from private_disclosure import configured_terms, contains_private_term

ROOT = Path(__file__).resolve().parents[1]
RELEASE = {"src/live-session.mjs", "src/original-paper.mjs", "data/original-track-map.json","data/historical-paper-results.csv", "data/historical-paper-curves.csv","index.html", "private-paper.html", "private-theses.html", "src/private-paper.mjs", "src/private-paper-view.mjs", "src/private-theses.mjs", "src/private-theses-view.mjs", "research.html", "styles.css", "favicon.svg", "logo.svg", "src/site.mjs", "src/glossary.mjs", "src/algorithm-detail.mjs", "src/operations-audit.mjs", "src/operation-lots.mjs", "src/metrics.mjs", "src/learning.mjs", "src/learning-view.mjs", "src/paper-methods.mjs", "src/paper-ledger.mjs", "src/competition-roster.mjs", "src/paper-feed.mjs", "data/demo.json", "data/fx-forecast-ledger.json", "data/sec-filings.json", "data/competition-roster.json", "data/strategy-candidates.json", "data/institutional-paper-feed.json", "data/public-theses.json", "data/public-closes.json", "data/forward-open-il039.json", "src/public-theses.mjs"}
REPOSITORY = RELEASE | {"tests/live-session.test.mjs", "scripts/private_disclosure.py", "scripts/test_private_disclosure.py", "README.md", "docs/SCIENTIFIC_PARITY.md", "scripts/audit_public.py", "scripts/operational_status.py", "scripts/test_operational_status.py", "scripts/satellite_pilot.py", "scripts/test_satellite_pilot.py", "scripts/build_operations_audit.py", "scripts/test_operations_audit.py", "scripts/build_opening_plan.py", "scripts/test_opening_plan.py", "scripts/build_execution_history.py", "scripts/test_execution_history.py", "docs/RUNBOOK_PRODUCCION.md", ".github/workflows/operational-status.yml", "scripts/refresh_ecb.py", "scripts/test_ecb.py", "scripts/advance_fx.py", "scripts/test_advance_fx.py", "scripts/refresh_sec.py", "scripts/test_sec.py", "scripts/refresh_ecb_yield.py", "scripts/test_ecb_yield.py", "scripts/yahoo_source.py", "scripts/test_yahoo_source.py", "data/universe-xnys.json", "scripts/requirements-yahoo.txt", "data/public-paper-book.json", "scripts/public_market_runner.py", "scripts/test_public_market_runner.py", "scripts/classic_503.py", "scripts/test_classic_503.py", "scripts/classic_503_book.py", "scripts/test_classic_503_book.py", "scripts/monthly_selection.py", "scripts/test_monthly_selection.py", "scripts/monthly_paper.py", "scripts/test_monthly_paper.py", "scripts/monthly_factors.py", "scripts/test_monthly_factors.py", "scripts/weekly_selection.py", "scripts/test_weekly_selection.py", "scripts/weekly_baselines.py", "scripts/test_weekly_baselines.py", "scripts/weekly_models.py", "scripts/test_weekly_models.py", "scripts/weekly_lightgbm.py", "scripts/test_weekly_lightgbm.py", "scripts/weekly_lstm.py", "scripts/test_weekly_lstm.py", "scripts/lstm_walkforward.py", "scripts/test_lstm_walkforward.py", "scripts/requirements-research.txt", "data/monthly-paper-book.json", "data/classic-503-book.json", ".github/workflows/public-market.yml", "scripts/paper_feed.py", "scripts/test_paper_feed.py", "tests/metrics.test.mjs", "tests/learning.test.mjs", "tests/paper-methods.test.mjs", "tests/paper-ledger.test.mjs", "tests/competition-roster.test.mjs", "tests/algorithm-detail.test.mjs", "tests/operation-lots.test.mjs", "tests/paper-feed.test.mjs", "tests/private-paper.test.mjs", "tests/private-theses.test.mjs", "scripts/forward_open_il039.py", "scripts/test_forward_open_il039.py", ".github/workflows/forward-open-il039.yml", ".github/workflows/pages.yml", ".github/workflows/fx-ledger.yml", ".github/workflows/sec-filings.yml"}
# Institutionally reviewed web/PDF research templates and their source manifest.
RELEASE |= {"src/thesis-report.mjs", "src/thesis-report.css", "src/thesis-insights.mjs", "src/thesis-source-structure.mjs", "src/thesis-historical-figures.mjs", "data/thesis-reports.json", "src/financial-sankey.mjs", "src/financial-sankey.css", "data/financial-sankeys.json"}
REPOSITORY |= RELEASE | {"tests/financial-sankey.test.mjs", "tests/thesis-report.test.mjs", "tests/thesis-historical-figures.test.mjs", "tests/thesis-source-depth.test.mjs", "scripts/build_thesis_pdfs.py", "scripts/test_thesis_pdf_builder.py"}
REPOSITORY.add("docs/NAUT_RESEARCH_BRIEF_2026-11-05.md")
if (ROOT / "forward_open_state/il039-lock.json").is_file():
    REPOSITORY.add("forward_open_state/il039-lock.json")
# Review-scoped institutional Debate Alpha code. None enters static Pages RELEASE.
REPOSITORY |= {
    "multi_agent/run.py",
    "multi_agent/README.md",
    "multi_agent/tests/test_run.py",
    ".github/workflows/multi_agent_paper.yml",
}
# The prospective-only journal is initially absent. Admit its exact owned path
# only once a scheduled source-verified paper run creates it.
if (ROOT / "multi_agent_state/ledger.json").is_file():
    REPOSITORY.add("multi_agent_state/ledger.json")
engine_manifest=ROOT/"data/engine-files.json"
if engine_manifest.exists():
    engine_paths=json.loads(engine_manifest.read_text(encoding="utf8")).get("paths",[])
    if not engine_paths or any(not isinstance(p,str) or p.startswith("/") or ".." in p.split("/") for p in engine_paths):
        raise ValueError("Invalid engine path allowlist")
    REPOSITORY |= set(engine_paths) | {"data/engine-files.json"}
    for directory in ["market_data/snapshots/XNYS","weekly_ml_state/forecasts","weekly_ml_daily_state/forecasts"]:
        REPOSITORY |= {str(p.relative_to(ROOT)) for p in (ROOT/directory).rglob("*.json") if p.is_file()}
# Admit the two dated engine journals to the source audit only. Pages never copies them.
for directory in ("tfg_state/signals", "weekly_ml_state/evaluations"):
    REPOSITORY |= {
        str(path.relative_to(ROOT))
        for path in (ROOT/directory).glob("*.json")
        if path.is_file() and re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", path.name)
    }
# Buy The Dip semantic reviews are internal machine outputs keyed by exactly
# eleven-character YouTube video IDs. They are never added to RELEASE or dist.
REPOSITORY |= {
    str(p.relative_to(ROOT))
    for p in (ROOT/"buy_the_dip_state/reviews").glob("*.json")
    if p.is_file() and re.fullmatch(r"[A-Za-z0-9_-]{11}\.json", p.name)
}
issues = []
try:
    private_terms = configured_terms()
except ValueError as error:
    issues.append(str(error))
    private_terms = ()
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
for page in ("index.html", "research.html", "private-paper.html", "private-theses.html"):
 if not (ROOT/page).exists(): continue
 links=Links()
 links.feed((ROOT/page).read_text(encoding="utf8"))
 for url in links.references:
        if url.startswith("#"): continue
        if url.startswith("https://"):
            if not (url.startswith("https://idealab2026.github.io/") or url.startswith("https://github.com/idealab2026/")):
                issues.append("Non-institutional external link")
        elif url.startswith("./"):
            local_path, separator, query = url[2:].partition("?")
            if local_path not in RELEASE or (separator and not (re.fullmatch(r"v=[a-f0-9]{12}", query) or local_path == "index.html" and query in {"view=competition", "view=theses"})):
                issues.append("Dependency not on release allowlist")
        else: issues.append("Unexpected link or source type")
for path in sorted(files):
    if path not in REPOSITORY: continue
    source=(ROOT/path).read_text(encoding="utf8")
    if contains_private_term(path+"\n"+source, private_terms):
        issues.append("Private disclosure guard rejected repository content in "+path)
    if path in RELEASE or path == "README.md" or path.startswith("docs/"):
        if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",source):
            issues.append("Email address found in public content")
    if path in RELEASE or path == "README.md" or path.startswith("docs/"):
        if re.search(r"\bTF[GM]\b|\bpersonal_[a-z0-9_]+\b", source, re.I):
            issues.append("Noninstitutional origin label found in public output")
    if re.search(r"-----BEGIN [^-]+PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{30,}",source):
        issues.append("Credential-like content")
    if re.search(r"https?://(?:localhost|127\.0\.0\.1|[^\s/]*\.workers\.dev)",source,re.I):
        issues.append("Unexpected local or backend reference")
sample=ROOT/"data/demo.json"
if sample.exists():
    try:
        demo = json.loads(sample.read_text(encoding="utf8"))
        if demo.get("meta",{}).get("data_class")!="synthetic":
            issues.append("Dataset not admitted for a public synthetic demonstration")
        admitted = {"MSFT": "https://www.microsoft.com/investor/reports/ar26/index.html",
                    "RKLB": "https://investors.rocketlabcorp.com/resources/investor-faqs"}
        catalog = demo.get("issuerCatalog", {})
        issuers = catalog.get("issuers", [])
        if {x.get("ticker") for x in issuers} != set(admitted) or len(issuers) != len(admitted):
            issues.append("Issuer cohort has not passed independent admission")
        for issuer in issuers:
            if issuer.get("admission", {}).get("primary_source") != admitted.get(issuer.get("ticker")):
                issues.append("Issuer lacks independently reviewed primary evidence")
    except (OSError,ValueError):
        issues.append("Invalid dataset")
publication=ROOT/"data/public-theses.json"
if publication.exists():
    try:
        text=publication.read_text(encoding="utf-8")
        doc=json.loads(text)
        if doc.get("schema") != "midas_public_theses_v1" or doc.get("data_class") != "author_approved_public_research_snapshot" or not isinstance(doc.get("records"), list) or len(doc["records"]) != 26:
            issues.append("Unapproved thesis publication contract")
        if re.search(r"https?://|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|personal_[a-z0-9_]+",text,re.I):
            issues.append("Private links or origins in thesis publication")
    except (OSError, ValueError, TypeError):
        issues.append("Unreadable thesis publication")
report_manifest=ROOT/"data/thesis-reports.json"
if report_manifest.exists():
    try:
        doc=json.loads(report_manifest.read_text(encoding="utf8"))
        rows=doc.get("reports",[])
        if doc.get("schema")!="midas_canonical_web_reports_v1" or not isinstance(rows,list) or len(rows)>25:
            issues.append("Canonical thesis publication contract invalid")
        else:
            symbols=set()
            for entry in rows:
                symbol=entry.get("ticker","")
                body=entry.get("source_text","")
                if symbol in symbols or not re.fullmatch(r"[A-Z0-9]{1,8}(?:\.[A-Z]{1,3})?",symbol) or entry.get("publication_gate")!="approved" or not isinstance(body,str) or not 500<=len(body)<=180000 or re.search(r"https?://|personal_[a-z0-9_]+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",body,re.I):
                    issues.append("Unreviewed or unsafe corporate report")
                symbols.add(symbol)
    except (OSError,ValueError,TypeError,AttributeError):
        issues.append("Unreadable canonical report manifest")
if issues:
    print("PUBLIC RELEASE REJECTED:",*sorted(set(issues)),sep="\n- ")
    sys.exit(1)
print("OK: allowlist, source scanning, institutional links and synthetic demonstration")
