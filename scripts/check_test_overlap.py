#!/usr/bin/env python3
"""Near-duplicate check between a generated FAG corpus and held-out test files.

The generated corpus is training data; the CSVs you evaluate on are held out.
This script is the boundary check between them, and it is deliberately
standalone: nothing else in the pipeline reads the test files, so they are only
ever opened when YOU run this, with paths YOU pass.

    python scripts/check_test_overlap.py \
        --generated output/vrm_fag_conversations.jsonl \
        --test-csv /path/to/single_turn.csv /path/to/multi_turn.csv \
        --threshold 0.6 \
        --write-clean output/vrm_fag_conversations.clean.jsonl

Method: word 5-gram Jaccard similarity, with an inverted index so only
candidates sharing at least one shingle are compared. Pure stdlib — no numpy,
no sklearn. Exact matches on normalised text are reported separately.
"""

import argparse
import ast
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

csv.field_size_limit(10 ** 9)

SHINGLE_N = 5
_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def normalise(text):
    return _WS.sub(" ", _PUNCT.sub(" ", str(text).lower())).strip()


def shingles(text, n=SHINGLE_N):
    words = normalise(text).split()
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


# ── loading ──────────────────────────────────────────────────────

def _flatten_cell(value):
    """Test CSV cells may hold a python-literal list of {role, Content} dicts."""
    text = str(value)
    if text.lstrip().startswith("["):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                out = []
                for item in parsed:
                    if isinstance(item, dict):
                        for key in ("Content", "content", "text"):
                            if key in item:
                                out.append(str(item[key]))
                                break
                    else:
                        out.append(str(item))
                return " ".join(out)
        except (ValueError, SyntaxError):
            pass
    return text


def load_test_docs(paths, columns):
    docs = []
    for path in paths:
        if not os.path.exists(path):
            sys.exit(f"test file not found: {path}")
        with open(path, encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f), start=1):
                parts = [_flatten_cell(row[c]) for c in columns if c in row and row[c]]
                if parts:
                    docs.append((f"{os.path.basename(path)}:{i}", " ".join(parts)))
    return docs


def load_generated_docs(path):
    docs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = " ".join(str(m.get("content", "")) for m in rec.get("messages") or [])
            docs.append((rec.get("conversation_id", "?"), text, rec))
    return docs


# ── main ─────────────────────────────────────────────────────────

def main(args):
    test_docs = load_test_docs(args.test_csv, args.text_columns)
    gen_docs = load_generated_docs(args.generated)
    print(f"test docs: {len(test_docs)}   generated docs: {len(gen_docs)}")

    test_sh = {tid: shingles(t) for tid, t in test_docs}
    exact = {normalise(t): tid for tid, t in test_docs}

    index = defaultdict(list)
    for tid, sh in test_sh.items():
        for s in sh:
            index[s].append(tid)

    findings = []
    clean = []
    exact_hits = 0
    for cid, text, rec in gen_docs:
        if normalise(text) in exact:
            exact_hits += 1
            findings.append((1.0, cid, exact[normalise(text)]))
            continue
        sh = shingles(text)
        cand = Counter()
        for s in sh:
            for tid in index.get(s, ()):
                cand[tid] += 1
        best, best_id = 0.0, None
        for tid, _ in cand.most_common(args.max_candidates):
            score = jaccard(sh, test_sh[tid])
            if score > best:
                best, best_id = score, tid
        if best >= args.threshold:
            findings.append((best, cid, best_id))
        else:
            clean.append(rec)

    findings.sort(reverse=True)
    print(f"\nexact normalised matches: {exact_hits}")
    print(f"records at or above threshold {args.threshold}: {len(findings)}"
          f"  ({100.0 * len(findings) / max(len(gen_docs), 1):.2f}% of corpus)")
    if findings:
        print("\nworst overlaps:")
        for score, cid, tid in findings[:args.show]:
            print(f"  {score:.3f}  {cid}  ~  {tid}")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump([{"similarity": s, "conversation_id": c, "test_row": t}
                       for s, c, t in findings], f, indent=2)
        print(f"\nreport -> {args.report}")

    if args.write_clean:
        os.makedirs(os.path.dirname(args.write_clean) or ".", exist_ok=True)
        with open(args.write_clean, "w", encoding="utf-8") as f:
            for rec in clean:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"clean corpus ({len(clean)} records) -> {args.write_clean}")

    return 1 if findings else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generated", required=True, help="generated corpus .jsonl")
    ap.add_argument("--test-csv", required=True, nargs="+", help="held-out test CSV file(s)")
    ap.add_argument("--text-columns", nargs="+", default=["input", "original_response"],
                    help="CSV columns holding conversation text")
    ap.add_argument("--threshold", type=float, default=0.6,
                    help="Jaccard similarity at or above which a record is flagged")
    ap.add_argument("--max-candidates", type=int, default=50,
                    help="candidate test rows scored per generated record")
    ap.add_argument("--show", type=int, default=20, help="how many overlaps to print")
    ap.add_argument("--report", default=None, help="write findings as JSON here")
    ap.add_argument("--write-clean", default=None,
                    help="write records below threshold to this .jsonl")
    sys.exit(main(ap.parse_args()))
