"""Safe, opt-in staging of newly appended S1 Outbox requests as queued cards.

Never edits the live Outbox or queue and never creates real Sage receipts,
WebClip messages, or dispatches. Historical Outbox bytes are pinned at
bootstrap, so old requests cannot be automatically replayed.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re


def _write_exclusive(path, content):
    """Standalone, create-only 0600 write; no AffectControl import required."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())

SCHEMA = "affectcontrol-sage-outbox-staging-v1"
HEADING = re.compile(r"(?m)^### \[([^\]\r\n]+)\]\s*$")
FIELD = re.compile(r"^- \*\*(.+?)\*\*[:：]\s*(.*)$")
NEW_S1 = re.compile(r"^20\d{2}-\d\d-\d\d \d\d:\d\d:\d\d 请求：(TASK-S1-[A-Za-z0-9_-]+)$")
SAFE_TASK = re.compile(r"^TASK-S1-[A-Za-z0-9_-]{1,100}$")
SAFE_NATIVE = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def read(path):
    path=Path(path)
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= 20000000:
        raise ValueError("missing, unsafe or oversized source")
    return path.read_bytes()


def bootstrap(source, out):
    raw=read(source)
    raw.decode("utf-8")
    if not raw.endswith(b"\n"):
        raise ValueError("incomplete Outbox at bootstrap")
    report={
        "schema": SCHEMA,
        "baseline_bytes":len(raw),
        "baseline_sha256":digest(raw),
        "baseline_utc":datetime.now(timezone.utc).isoformat(),
        "historical_requests_replayed":0,
        "real_sage_receipt":None,
    }
    dest=Path(out)
    dest.parent.mkdir(parents=True,exist_ok=True)
    _write_exclusive(dest,(json.dumps(report,sort_keys=True,indent=2)+"\n").encode())
    return report


def parse_append(text):
    if not text.strip():
        return []
    sections=HEADING.split(text)
    if sections[0].strip():
        raise ValueError("append does not start at a new heading")
    proposed=[]
    for i in range(1,len(sections)-1,2):
        match=NEW_S1.fullmatch(sections[i])
        if match is None:
            # Never acknowledge-and-skip a malformed original S1 request.
            # Unlike an unrelated status/reply notice, this would silently
            # advance the input cursor and permanently lose the new task.
            if "请求：" in sections[i] and "新任务请求（来自 S1）" in sections[i+1]:
                raise ValueError("malformed S1 request header")
            continue  # Unrelated result/notification, never a new task.
        f={}
        for line in sections[i+1].splitlines():
            m=FIELD.match(line.strip())
            if m:
                if m.group(1) in f:
                    raise ValueError("repeated request field")
                f[m.group(1)]=m.group(2).strip()
        if f.get("类型") != "新任务请求（来自 S1）":
            # A syntactically valid TASK-S1 new-request heading with an
            # incomplete body must not advance the durable cursor: the
            # remaining body may be appended by the source writer later.
            raise ValueError("invalid or incomplete S1 request type")
        native=f.get("s1_ref")
        card=f.get("任务ID（建议）")
        goal=f.get("目标")
        if not isinstance(native,str) or not SAFE_NATIVE.fullmatch(native):
            raise ValueError("invalid native S1 ref")
        if not isinstance(card,str) or not SAFE_TASK.fullmatch(card) or card!=match.group(1):
            raise ValueError("provider ID mismatch")
        if not isinstance(goal,str) or not goal or len(goal)>2000 or "### [" in goal:
            raise ValueError("missing or unsafe task goal")
        risk=f.get("risk（建议）") or "unknown"
        if risk not in ("low","medium","high","unknown"):
            raise ValueError("unrecognized risk")
        proposed.append({
            "native":native,"card":card,"goal":goal,"risk":risk,
            "source_entry_sha256":digest((sections[i]+"\n"+sections[i+1]).encode()),
        })
        if len(proposed)>300:raise ValueError("too many staged tasks")
    if len({x["card"] for x in proposed})!=len(proposed):
        raise ValueError("duplicate provider ID in appended requests")
    if len({x["native"] for x in proposed})!=len(proposed):
        raise ValueError("duplicate native S1 task in appended requests")
    return proposed


def stage(source, baseline, queue, out):
    manifest=json.loads(read(baseline))
    if manifest.get("schema")!=SCHEMA:
        raise ValueError("unsupported baseline")
    raw=read(source)
    n=manifest.get("baseline_bytes")
    if type(n) is not int or n<1 or n>len(raw):
        raise ValueError("source is shorter than original baseline")
    if digest(raw[:n])!=manifest.get("baseline_sha256"):
        raise ValueError("original Outbox prefix has been changed")
    suffix=raw[n:]
    tasks=parse_append(suffix.decode("utf-8"))
    if not tasks:raise ValueError("no new S1 requests to stage")
    previous=read(queue)
    doc=previous.decode("utf-8")
    current=set(re.findall(r"(?m)^### \[(TASK-[^\]\r\n]+)\]",doc))
    if any(x["card"] in current for x in tasks):
        raise ValueError("proposed task card ID already in queue")
    for x in tasks:
        doc+=(
            "\n\n### ["+x["card"]+"]\n"
            "- **状态**：queued\n"
            "- **来源**：S1-local-staging-not-production\n"
            "- **s1_ref**："+x["native"]+"\n"
            "- **描述**："+x["goal"]+"\n"
            "- **risk**："+x["risk"]+"\n"
            "- **auto_run**：no\n"
            "- **requires_user_confirm**：yes\n"
            "- **router_decision**：STAGING_NOT_DISPATCHABLE\n"
        )
    rendered=doc.encode("utf-8")
    summary={
        "schema":SCHEMA,
        "origin":"private-staging-no-live-Sage-cards",
        "baseline_sha256":manifest["baseline_sha256"],
        "new_outbox_suffix_sha256":digest(suffix),
        "original_queue_sha256":digest(previous),
        "staged_queue_sha256":digest(rendered),
        "new_candidate_count":len(tasks),
        "request_evidence":[
            {"source_entry_sha256":x["source_entry_sha256"],
             "native_ref_sha256":digest(x["native"].encode()),
             "provider_card_id_sha256":digest(x["card"].encode())}
            for x in tasks],
        "real_receiver_accepted":None,
        "real_webclip_message_id":None,
        "independent_outcome_accepted":None,
        "actual_user_deadline":None,
        "auto_dispatch_enabled":False,
        "evidence_level":"E1-staged-ingest-not-real-receiver",
    }
    root=Path(out)
    root.mkdir(parents=True,exist_ok=False)
    _write_exclusive(root/"staged-queue.md",rendered)
    _write_exclusive(root/"receipt.json",(json.dumps(summary,sort_keys=True,indent=2)+"\n").encode())
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="action",required=True)
    b=sub.add_parser("bootstrap");b.add_argument("--source",required=True)
    b.add_argument("--baseline",required=True)
    s=sub.add_parser("stage");s.add_argument("--source",required=True)
    s.add_argument("--baseline",required=True);s.add_argument("--queue",required=True)
    s.add_argument("--out",required=True)
    a=p.parse_args()
    r=bootstrap(a.source,a.baseline) if a.action=="bootstrap" else stage(a.source,a.baseline,a.queue,a.out)
    print(json.dumps({"schema":r["schema"],"staged_candidates":r.get("new_candidate_count",0),
                      "real_receiver_accepted":None,"production_dispatch_changed":False}))


if __name__=="__main__":
    main()
