"""Separate closing marks for passive NAV only; never an OHLC trading overlay."""
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import tempfile

from market_data.revisions import load_effective
from market_data.snapshot import _digest, provider_symbol
from market_data.verified_chart import CLOSE, reconstruct

SCHEMA="midas.xnys_passive_close_marks.v1"


def directory(root,day):
    return Path(root)/"XNYS"/(day+".closes")


def load_marks(root,day):
    effective=load_effective(root,day)
    result={};hashes=[]
    for path in sorted(directory(root,day).glob("*.json")):
        doc=json.loads(path.read_text())
        if (set(doc)!={"schema","session","base_sha256","captured_at_utc","marks","evidence","sha256"} or
            doc["schema"]!=SCHEMA or doc["session"]!=day or doc["base_sha256"]!=effective["base"]["sha256"] or
            _digest(doc)!=doc["sha256"] or path.stem!=doc["sha256"] or not doc["marks"] or
            set(doc["marks"])!=set(doc["evidence"])):
            raise ValueError("Invalid passive close evidence file")
        stamp=datetime.fromisoformat(doc["captured_at_utc"])
        original=datetime.fromisoformat(effective["base"]["captured_at_utc"])
        if stamp.utcoffset().total_seconds()!=0 or stamp<original:
            raise ValueError("Passive mark predates source capture")
        for symbol,mark in doc["marks"].items():
            receipt=doc["evidence"][symbol]
            if (symbol not in effective["base"]["requested_symbols"] or symbol in result or
                receipt.get("method")!=CLOSE or receipt.get("session")!=day or
                receipt.get("provider_symbol")!=provider_symbol(symbol,day) or reconstruct(receipt)!=mark):
                raise ValueError("Unverified or duplicate passive mark")
            result[symbol]=mark
        hashes.append(doc["sha256"])
    return result,hashes,effective


def append_marks(root,day,marks,evidence,*,captured_at_utc):
    existing,_,effective=load_marks(root,day)
    if not marks or set(marks)!=set(evidence) or not set(marks)<=set(effective["missing"])-set(existing):
        raise ValueError("Close marks must address genuinely missing observations")
    for symbol,mark in marks.items():
        receipt=evidence[symbol]
        if (receipt.get("method")!=CLOSE or receipt.get("session")!=day or
            receipt.get("provider_symbol")!=provider_symbol(symbol,day) or reconstruct(receipt)!=mark):
            raise ValueError("Close mark and evidence disagree")
    stamp=datetime.fromisoformat(captured_at_utc)
    if stamp.utcoffset().total_seconds()!=0 or stamp<datetime.fromisoformat(effective["base"]["captured_at_utc"]):
        raise ValueError("Invalid passive capture chronology")
    doc={"schema":SCHEMA,"session":day,"base_sha256":effective["base"]["sha256"],
         "captured_at_utc":captured_at_utc,"marks":marks,"evidence":evidence}
    doc["sha256"]=_digest(doc)
    folder=directory(root,day);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(doc["sha256"]+".json")
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=folder,delete=False) as out:
        temp=Path(out.name)
        out.write(json.dumps(doc,sort_keys=True,indent=2,allow_nan=False)+"\n")
        out.flush();os.fsync(out.fileno())
    try:
        os.link(temp,path)
    finally:
        temp.unlink(missing_ok=True)
    load_marks(root,day)
    return path,doc


def passive_marks(root,day):
    """Only this explicitly passive API merges close marks; canonical OHLC does not."""
    marks,hashes,effective=load_marks(root,day)
    return {**marks,**effective["bars"]},{"snapshot_sha256":effective["base"]["sha256"],
        "effective_sha256":effective["effective_sha256"],"closing_mark_hashes":hashes,
        "closing_mark_scope":"passive_nav_only"}
