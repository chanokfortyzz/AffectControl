"""Compare frozen and subsequently corrected labels without rewriting old results."""
from __future__ import annotations

import argparse
import json
from affectcontrol.temporal_labels import audit_revisions, load_cases, load_events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, help="append-only label event JSONL")
    parser.add_argument("--cases", required=True, help="cases JSONL with sample_id, observed_at")
    parser.add_argument("--frozen-at", required=True, help="knowledge cutoff used for original evaluation")
    parser.add_argument("--reviewed-at", required=True, help="later knowledge cutoff")
    args = parser.parse_args()
    result = audit_revisions(
        load_events(args.events), load_cases(args.cases),
        frozen_at=args.frozen_at, reviewed_at=args.reviewed_at,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
