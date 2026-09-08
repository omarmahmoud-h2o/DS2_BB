import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
from collections import Counter

import config
from utils import validate_conversation


def main(input_file, output_file):
    total = valid = 0
    kept = []
    status_counts = Counter()

    with open(input_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            record = json.loads(line)
            ok, errors = validate_conversation(record, config.RISK_CATEGORIES)
            if ok:
                valid += 1
                kept.append(record)
                status_counts[record["compliance_status"]] += 1
            else:
                print(f"[invalid] {record.get('conversation_id', '?')}: {errors}")

    print(f"\n{valid}/{total} conversations passed validation")
    print(f"compliance_status distribution (valid only): {dict(status_counts)}")

    if output_file:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for record in kept:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"wrote {len(kept)} validated conversations -> {output_file}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default=None,
                     help="if set, write only records that pass validation here")
    a = ap.parse_args()
    main(a.input, a.output)
