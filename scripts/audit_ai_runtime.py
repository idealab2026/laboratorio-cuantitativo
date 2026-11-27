#!/usr/bin/env python3
"""Admit only the pinned upstream browser runtime and scan its textual assets."""
from hashlib import sha256
from pathlib import Path
import re
from private_disclosure import configured_terms, contains_private_term

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'midas-ai/node_modules/@huggingface/transformers/dist'
ASSETS = {
    'transformers.min.js': 'aa5002b70e789798da263f5f99c62bd3e8fcd0c119258a493c40c180648365fa',
    'ort-wasm-simd-threaded.jsep.mjs': '08fb86ec433c78bfb032c5d84a68b8e8e5a8d81268fa39e24314179a5767a5b9',
    'ort-wasm-simd-threaded.jsep.wasm': 'c46655e8a94afc45338d4cb2b840475f88e5012d524509916e505079c00bfa39',
}
terms = configured_terms()
for name, expected in ASSETS.items():
    content = (DIST / name).read_bytes()
    if sha256(content).hexdigest() != expected:
        raise SystemExit('Unrecognised assistant runtime asset: ' + name)
    if name.endswith(('.js', '.mjs')):
        text = content.decode('utf-8')
        if contains_private_term(text, terms) or re.search(r'-----BEGIN [^-]+PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{30,}', text):
            raise SystemExit('Assistant runtime asset failed disclosure check: ' + name)
print('Assistant runtime: pinned hashes and disclosure check passed')
