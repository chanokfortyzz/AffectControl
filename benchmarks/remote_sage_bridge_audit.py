"""Direct, read-only Sage VPS Bridge snapshot and local S1 correlation census.

Uses existing SSH credentials in BatchMode, no remote writes or commands
beyond python3 reading four allowlisted files. The SSH session and
snapshot hashes are NOT signed Sage per-task reception acknowledgements.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

from benchmarks.capture_execution import _write_exclusive
from benchmarks.native_sage_continuity_audit import get_mappings

SCHEMA = "affectcontrol-real-remote-sage-bridge-readonly-v1"
REMOTE_SOURCE = r'''
import hashlib
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

base=Path(sys.argv[1])
if not base.is_dir() or base.is_symlink():
    raise ValueError("unavailable or unsafe Bridge root")
pairs=json.loads(MAPPING_JSON)
fields_re=re.compile(r"^- \*\*(.+?)\*\*[:：]\s*(.*)$")
card_re=re.compile(r"(?m)^### \[(TASK-[^\]\r\n]+)\]")
block_re=re.compile(r"(?m)^### \[([^\]\r\n]+)\]")
sources={}
contents={}
for filename in ("04-MAC_OUTBOX.md","02-MAC_TASK_QUEUE.md",
                 "02-MAC_TASK_QUEUE-ARCHIVE.md","07-MAC_TASK_STATE.json"):
    file=base/filename
    if file.is_symlink() or not file.is_file() or file.stat().st_size>30000000:
        raise ValueError("missing/unsafe Bridge source file")
    raw=file.read_bytes()
    sources[filename]={
        "sha256":hashlib.sha256(raw).hexdigest(),
        "size_bytes":len(raw),
        "modified_utc":datetime.fromtimestamp(file.stat().st_mtime,timezone.utc).isoformat(),
    }
    contents[filename]=raw.decode("utf-8")

def parse_lines(body):
    f={}
    for line in body.splitlines():
        m=fields_re.match(line.strip())
        if m:
            f.setdefault(m.group(1).strip(),m.group(2).strip())
    return f

chunks=block_re.split(contents["04-MAC_OUTBOX.md"])
requests=[]
for i in range(1,len(chunks)-1,2):
    if "请求：" not in chunks[i]:continue
    f=parse_lines(chunks[i+1])
    if f.get("类型") == "新任务请求（来自 S1）":
        requests.append((f.get("s1_ref"),f.get("任务ID（建议）")))

queue_records={}
archive_records={}
duplicate_count={}
for source,rec in (("02-MAC_TASK_QUEUE.md",queue_records),
                   ("02-MAC_TASK_QUEUE-ARCHIVE.md",archive_records)):
    items=card_re.split(contents[source])
    for i in range(1,len(items)-1,2):
        ident=items[i]
        rec.setdefault(ident,[]).append(parse_lines(items[i+1]))
    duplicate_count[source]=sum(len(v)>1 for v in rec.values())

watch=json.loads(contents["07-MAC_TASK_STATE.json"])
if not isinstance(watch,dict) or not isinstance(watch.get("tasks"),dict):
    raise ValueError("malformed Sage watchdog state")
state=watch["tasks"]
summary={
    "remote_bridge_files":sources,
    "remote_queue_distinct_card_ids":len(queue_records),
    "remote_archive_distinct_card_ids":len(archive_records),
    "remote_queue_duplicate_card_ids":duplicate_count["02-MAC_TASK_QUEUE.md"],
    "remote_archive_duplicate_card_ids":duplicate_count["02-MAC_TASK_QUEUE-ARCHIVE.md"],
    "remote_watchdog_task_count":len(state),
    "native_s1_mapping_rows_examined":len(pairs),
}
for key in (
    "exact_remote_outbox_submission_matches",
    "remote_outbox_missing_exact_pairs",
    "remote_outbox_duplicate_exact_pairs",
    "remote_queue_provider_id_present",
    "remote_queue_matching_s1_ref",
    "remote_archive_provider_id_present",
    "remote_archive_matching_s1_ref",
    "remote_archive_done_raw_untrusted",
    "remote_archive_done_source_grain_admissible",
    "remote_watchdog_provider_id_present",
):
    summary[key]=0
for native,provider in pairs:
    exact=sum(a==native and b==provider for a,b in requests)
    summary["exact_remote_outbox_submission_matches"]+=int(exact==1)
    summary["remote_outbox_missing_exact_pairs"]+=int(exact==0)
    summary["remote_outbox_duplicate_exact_pairs"]+=int(exact>1)
    qs=queue_records.get(provider,[])
    summary["remote_queue_provider_id_present"]+=int(bool(qs))
    summary["remote_queue_matching_s1_ref"]+=int(
        len(qs)==1 and qs[0].get("s1_ref")==native)
    archived=archive_records.get(provider,[])
    summary["remote_archive_provider_id_present"]+=int(bool(archived))
    summary["remote_archive_matching_s1_ref"]+=int(
        len(archived)==1 and archived[0].get("s1_ref")==native)
    done=any((f.get("状态") or f.get("status") or "").lower()
             in ("done","completed","closed") for f in archived)
    summary["remote_archive_done_raw_untrusted"]+=int(done)
    # Source is an aggregate archive file: any duplicate card IDs
    # break its global single-card grain for acceptance. Never choose
    # the most favorable duplicate outcome.
    summary["remote_archive_done_source_grain_admissible"]+=int(
        done and duplicate_count["02-MAC_TASK_QUEUE-ARCHIVE.md"]==0
        and len(archived)==1)
    summary["remote_watchdog_provider_id_present"]+=int(provider in state)
print(json.dumps(summary,sort_keys=True,separators=(",",":")))
'''


def _ssh_settings(push_script):
    raw=Path(push_script).read_text(encoding="utf-8")
    settings={}
    for line in raw.splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        k,value=line.split("=",1)
        if k in ("VPS_HOST","VPS_BRIDGE"):
            elements=shlex.split(value)
            if len(elements)!=1 or not elements[0] or "$" in elements[0]:
                raise ValueError("unsupported Sage Bridge SSH configuration")
            settings[k]=elements[0]
    if set(settings)!={"VPS_HOST","VPS_BRIDGE"}:
        raise ValueError("missing real Sage Bridge SSH configuration")
    return settings


def _script(mappings):
    # Task identifiers travel through the existing encrypted SSH stdin,
    # not shell command arguments or stdout.
    safe=[[native,provider] for native,provider,_,_ in mappings]
    return "MAPPING_JSON = "+repr(json.dumps(safe,ensure_ascii=True))+"\n"+REMOTE_SOURCE


def inspect_local_snapshot(bridge_root, mappings):
    """Execute exactly the remote read program on synthetic local fixtures."""
    script=_script(mappings)
    process=subprocess.run(
        [sys.executable,"-",str(bridge_root)],input=script,text=True,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,check=False)
    if process.returncode:
        raise ValueError("isolated source snapshot program rejected input")
    return json.loads(process.stdout)


def audit(s1_db, push_script):
    mappings=get_mappings(s1_db)
    if not mappings:
        raise ValueError("no native S1 Sage mappings available")
    if len(mappings)>10000 or len({v[1] for v in mappings})!=len(mappings):
        raise ValueError("invalid or ambiguous S1 Sage mappings")
    config=_ssh_settings(push_script)
    command="python3 - "+shlex.quote(config["VPS_BRIDGE"])
    proc=subprocess.run([
        "ssh","-o","BatchMode=yes","-o","ConnectTimeout=8",
        "-o","ServerAliveInterval=4","-o","ServerAliveCountMax=1",
        config["VPS_HOST"],command,
    ],input=_script(mappings),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
       text=True,timeout=30,check=False)
    if proc.returncode!=0:
        # Remote stderr can include confidential host paths/content.
        raise ValueError("read-only VPS SSH source census unavailable")
    try:
        observed=json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Sage VPS returned invalid census JSON") from exc
    if observed.get("native_s1_mapping_rows_examined")!=len(mappings):
        raise ValueError("remote source mapping cardinality mismatch")
    for filename in ("04-MAC_OUTBOX.md","02-MAC_TASK_QUEUE.md",
                     "02-MAC_TASK_QUEUE-ARCHIVE.md","07-MAC_TASK_STATE.json"):
        meta=observed.get("remote_bridge_files",{}).get(filename,{})
        if not re.fullmatch(r"[0-9a-f]{64}",str(meta.get("sha256",""))):
            raise ValueError("missing authentic source file digest")
    return {
        "schema":SCHEMA,
        "source_channel":"existing_ssh_authenticated_readonly_VPS_Bridge",
        "ssh_access_succeeded":True,
        "provider_source_receipt_cryptographically_signed":False,
        "native_s1_to_webclip_message_join_verified":None,
        "independent_business_task_acceptance":None,
        "source_authenticated_user_deadline":None,
        "evidence_level":"E1-live-remote-Bridge-file-inspection-only",
        "observations":observed,
        "warning":(
            "Remote files were fetched over existing SSH; their SHA256 hashes "
            "do not prove Sage task ingestion or independent provider "
            "attestation. Remote Outbox presence means file replication, "
            "not task acknowledgment. Archive done is untrusted if any "
            "duplicate card IDs exist. No production data is modified."
        ),
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db",required=True)
    p.add_argument("--push-script",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=audit(a.db,a.push_script)
    out=Path(a.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    _write_exclusive(out,(json.dumps(report,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({
        "ssh_access_succeeded":report["ssh_access_succeeded"],
        "remote_outbox_exact_matches":report["observations"]["exact_remote_outbox_submission_matches"],
        "remote_archive_duplicate_card_ids":report["observations"]["remote_archive_duplicate_card_ids"],
        "native_s1_to_webclip_message_join_verified":None,
        "evidence_level":report["evidence_level"],
    },indent=2))


if __name__=="__main__":
    main()
