"""Source-bound TEST-ONLY receipts for durable Sage Outbox staging.

An HMAC proves possession of the test secret, not that production Sage
actually ingested a task. Do not mistake laboratory signatures for
independent provider attribution, Bus messages or task acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

from benchmarks.sage_outbox_durable_stage import (
    _private_root, _read_state, _exclusive_lock, _recover_locked,
)
from benchmarks.sage_outbox_staged_intake import (
    _write_exclusive, digest, parse_append, read, HEADING, FIELD,
)

SCHEMA = "affectcontrol-private-staging-test-hmac-receipt-v1"
CARD = re.compile(r"^TASK-S1-[A-Za-z0-9_-]{1,100}$")
SHA = re.compile(r"^[0-9a-f]{64}$")


def canon(data):
    return json.dumps(data,sort_keys=True,ensure_ascii=False,
                      separators=(",",":"),allow_nan=False).encode("utf-8")


def _test_key(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size!=32:
        raise ValueError("test signing key must be a regular 32-byte file")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise ValueError("test signing key permissions must be private")
    return path.read_bytes()


def _cards(raw):
    parts=HEADING.split(raw.decode("utf-8"))
    cards={}
    for n in range(1,len(parts)-1,2):
        name=parts[n]
        if not CARD.fullmatch(name):
            continue
        if name in cards:
            raise ValueError("duplicate staged queue card")
        fields={}
        for line in parts[n+1].splitlines():
            match=FIELD.match(line.strip())
            if match:
                if match.group(1) in fields:
                    raise ValueError("duplicate staged queue field")
                fields[match.group(1)]=match.group(2).strip()
        cards[name]=fields
    return cards


def _cross_check(root, source):
    root=_private_root(root)
    if (root/"pending.json").exists():
        raise ValueError("pending staging commit has not been recovered")
    state,state_blob=_read_state(root)
    q=read(root/"queue.md")
    if digest(q)!=state["queue_sha256"]:
        raise ValueError("committed staged queue digest mismatch")
    src=read(source)
    pos=state["cursor_bytes"]
    boot=state["bootstrap_bytes"]
    if len(src)<pos or digest(src[:pos])!=state["source_prefix_sha256"]:
        raise ValueError("original source bytes no longer match cursor")
    if digest(src[:boot])!=state["bootstrap_source_sha256"]:
        raise ValueError("historic baseline source changed")
    cards=_cards(q)
    claims=[]
    for provider_hash,record in sorted(state["accepted"].items()):
        if not SHA.fullmatch(provider_hash):
            raise ValueError("invalid staged provider hash")
        start=record.get("source_chunk_start")
        end=record.get("source_chunk_end")
        chunk_sha=record.get("source_chunk_sha256")
        if (type(start) is not int or type(end) is not int or
                start < boot or end > pos or start >= end or not SHA.fullmatch(str(chunk_sha))):
            raise ValueError("invalid recorded source byte boundaries")
        chunk=src[start:end]
        if digest(chunk)!=chunk_sha:
            raise ValueError("staged source chunk digest mismatch")
        items=parse_append(chunk.decode("utf-8"))
        matched=[
            item for item in items
            if digest(item["card"].encode("utf-8"))==provider_hash
        ]
        if len(matched)!=1:
            raise ValueError("source chunk missing original staged task")
        item=matched[0]
        if (digest(item["native"].encode("utf-8"))!=record["native_ref_sha256"] or
                item["source_entry_sha256"]!=record["source_entry_sha256"]):
            raise ValueError("original staged source task digest mismatch")
        card=cards.get(item["card"])
        if card is None:
            raise ValueError("corresponding committed staging card missing")
        expected={
            "s1_ref": item["native"],
            "来源":"S1-staged-only-not-production",
            "auto_run":"no",
            "requires_user_confirm":"yes",
            "router_decision":"STAGING_NOT_DISPATCHABLE",
        }
        if any(card.get(k)!=v for k,v in expected.items()):
            raise ValueError("staging card provenance or no-dispatch guard changed")
        claims.append({
            "provider_id_sha256":provider_hash,
            "native_s1_ref_sha256":record["native_ref_sha256"],
            "original_request_entry_sha256":record["source_entry_sha256"],
            "source_chunk_sha256":chunk_sha,
            "source_chunk_start":start,
            "source_chunk_end":end,
            "committed_state_sha256":digest(state_blob),
            "committed_queue_sha256":digest(q),
            "source_cursor_sha256":state["source_prefix_sha256"],
            "claim":"private_staging_card_committed_not_dispatched",
            "real_webclip_bus_message_id":None,
            "independent_task_acceptance":None,
        })
    if len(claims)!=len(state["accepted"]):
        raise ValueError("staging receipt cardinality mismatch")
    return claims


def issue(root, source, key_file, out):
    """Lab-only HMAC receipt; all paths must be private staging/test paths."""
    key=_test_key(key_file)
    root=_private_root(root)
    with _exclusive_lock(root):
        if (root/"pending.json").exists():
            raise ValueError("recover pending transaction before attesting")
        claims=_cross_check(root,source)
        if not claims:
            raise ValueError("cannot sign zero staged tasks")
        bundle={
            "schema":SCHEMA,
            "signed_at_utc":datetime.now(timezone.utc).isoformat(),
            "signer_role":"research_lab_staging_controller_only",
            "key_fingerprint_sha256":digest(key),
            "receipts":[],
            "production_sage_intake_signed":False,
        }
        for claim in claims:
            message={"schema":SCHEMA,"signed_at_utc":bundle["signed_at_utc"],
                     "signer_role":bundle["signer_role"],"claim":claim}
            tag=hmac.new(key,canon(message),hashlib.sha256).hexdigest()
            bundle["receipts"].append({"message":message,"hmac_sha256":tag})
        path=Path(out)
        if path.parent.resolve()!=root.resolve() or path.is_symlink():
            raise ValueError("test receipts must be written into private staging root")
        _write_exclusive(path,(json.dumps(bundle,sort_keys=True,indent=2)+"\n").encode("utf-8"))
        return {"schema":SCHEMA,"test_receipt_count":len(claims),
                "production_sage_intake_signed":False,"independently_provider_verified":False}


def verify(root, source, key_file, receipt_path):
    """Recompute source, queue, state and MAC in a separate invocation."""
    key=_test_key(key_file)
    root=_private_root(root)
    path=Path(receipt_path)
    if path.parent.resolve()!=root.resolve() or path.is_symlink():
        raise ValueError("untrusted receipt location")
    with _exclusive_lock(root):
        claims=_cross_check(root,source)
        bundle=json.loads(read(path))
        if (bundle.get("schema")!=SCHEMA or bundle.get("signer_role")!="research_lab_staging_controller_only"
                or bundle.get("key_fingerprint_sha256")!=digest(key)
                or bundle.get("production_sage_intake_signed") is not False):
            raise ValueError("invalid test-only receipt metadata")
        receipts=bundle.get("receipts")
        if not isinstance(receipts,list) or len(receipts)!=len(claims):
            raise ValueError("receipt count mismatch")
        observed={}
        for entry in receipts:
            message=entry.get("message",{})
            if (message.get("schema")!=SCHEMA or message.get("signer_role")!=bundle["signer_role"]
                    or message.get("signed_at_utc")!=bundle.get("signed_at_utc")):
                raise ValueError("receipt binding mismatch")
            tag=hmac.new(key,canon(message),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(str(entry.get("hmac_sha256","")),tag):
                raise ValueError("test signature mismatch")
            keyid=message.get("claim",{}).get("provider_id_sha256")
            if not isinstance(keyid,str) or keyid in observed:
                raise ValueError("duplicate or invalid signed task")
            observed[keyid]=message.get("claim")
        original={a["provider_id_sha256"]:a for a in claims}
        if observed!=original:
            raise ValueError("signed claims do not match verified committed source")
        return {
            "schema":SCHEMA, "test_receipt_count":len(receipts),
            "source_state_and_queue_verified":True,
            "hmac_matches_test_key":True,
            "independent_sage_provider_authentication":False,
            "production_bus_join":False,
            "evidence_level":"E1-private-test-signature-only",
        }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    for name in ("issue","verify"):
        a=sub.add_parser(name)
        a.add_argument("--root",required=True)
        a.add_argument("--source",required=True)
        a.add_argument("--test-key-file",required=True)
        a.add_argument("--receipt",required=True)
    a=p.parse_args()
    if a.mode=="issue":
        result=issue(a.root,a.source,a.test_key_file,a.receipt)
    else:
        result=verify(a.root,a.source,a.test_key_file,a.receipt)
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":
    main()
