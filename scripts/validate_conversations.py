import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import argparse
from collections import Counter

from policy_categories import derive_policy_categories
from utils import validate_conversation


def main(input_file, output_file):
    total = valid = 0
    kept = []
    breach_counts = Counter()
    signal_counts = Counter()
    policy_counts = Counter()
    tier_counts = Counter()
    contestable = 0

    with open(input_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            record = json.loads(line)
            ok, errors = validate_conversation(record)
            if not ok:
                print(f"[invalid] {record.get('conversation_id', '?')}: {errors}")
                continue

            valid += 1
            kept.append(record)
            breach_counts[record["financial_advice_breach"]] += 1
            tier_counts[record["advice_tier"]] += 1
            contestable += bool(record.get("contestable"))
            for sig in record.get("signal_categories") or []:
                signal_counts[sig] += 1
            for cat, fired in derive_policy_categories(record).items():
                if fired:
                    policy_counts[cat] += 1

    print(f"\n{valid}/{total} conversations passed validation")
    print(f"financial_advice_breach: {dict(breach_counts)}")
    print(f"advice_tier:             {dict(tier_counts)}")
    print(f"contestable:             {contestable}")
    print("\nsignal category coverage:")
    for sig, n in signal_counts.most_common():
        print(f"  {n:>6}  {sig}")
    print("\nderived production policy categories:")
    for cat, n in policy_counts.most_common():
        print(f"  {n:>6}  {cat}")

    if output_file:
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for record in kept:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"\nwrote {len(kept)} validated conversations -> {output_file}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default=None,
                    help="if set, write only records that pass validation here")
    a = ap.parse_args()
    main(a.input, a.output)
