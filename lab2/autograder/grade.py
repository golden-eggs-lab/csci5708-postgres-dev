#!/usr/bin/env python3
"""
Gradescope Autograder — grade.py
CSCI 5708 Lab 2: B-tree Instrumentation
"""

import argparse
import json
import os
import re

RESULTS_PATH = "/autograder/results/results.json"


def write_results(tests, output="", score=None):
    total = sum(t.get("score", 0) for t in tests)
    max_total = sum(t.get("max_score", 0) for t in tests)
    results = {"output": output, "tests": tests}
    results["score"] = score if score is not None else total
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Grading complete: {total}/{max_total}")


def fail_result(msg, score=0):
    write_results(
        [{"name": "Autograder Error", "score": score, "max_score": 100, "output": msg}],
        output=msg, score=score,
    )


STAT_RE = re.compile(
    r"BTREE_LAB_STATS:\s*internal=(\d+)\s+leaf=(\d+)\s+splits=(\d+)"
)


def parse_stats_file(path):
    results = []
    if not os.path.exists(path):
        return results
    with open(path) as f:
        for line in f:
            m = STAT_RE.search(line)
            if m:
                results.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return results


def t(name, score, max_score):
    return {"name": name, "score": score, "max_score": max_score}


def grade(stats_dir):
    tests = []

    # 1. Compilation (10 pts)
    tests.append(t("1. Compilation", 10, 10))

    # 2. Output format (10 pts)
    all_stats = []
    for label in ["insert_10k", "point_lookup", "range_scan", "insert_small"]:
        all_stats.extend(parse_stats_file(os.path.join(stats_dir, f"{label}.txt")))

    if not all_stats:
        tests.append(t("2. Stats output format", 0, 10))
        for name, pts in [
            ("3. Insert: leaf visits > 0", 10),
            ("4. Insert: splits > 0", 15),
            ("5. Point lookup: leaf visits == 1", 15),
            ("6. Point lookup: internal visits >= 1", 10),
            ("7. Range scan: leaf visits >= 1", 10),
            ("8. Range scan: internal visits >= 1", 10),
            ("9. Small insert: correct behavior", 10),
        ]:
            tests.append(t(name, 0, pts))
        write_results(tests)
        return

    tests.append(t("2. Stats output format", 10, 10))

    # 3. Insert 10k — leaf visits > 0 (10 pts)
    insert_stats = parse_stats_file(os.path.join(stats_dir, "insert_10k.txt"))
    total_leaf_ins = sum(s[1] for s in insert_stats)
    total_splits_ins = sum(s[2] for s in insert_stats)

    tests.append(t("3. Insert: leaf visits > 0", 10 if total_leaf_ins > 0 else 0, 10))

    # 4. Insert 10k — splits > 0 (15 pts)
    tests.append(t("4. Insert: splits > 0", 15 if total_splits_ins > 0 else 0, 15))

    # 5. Point lookup — leaf visits == 1 (15 pts)
    lookup_stats = parse_stats_file(os.path.join(stats_dir, "point_lookup.txt"))
    lookup_last = lookup_stats[-1] if lookup_stats else None

    if lookup_last is not None:
        l_internal, l_leaf, _ = lookup_last
        tests.append(t("5. Point lookup: leaf visits == 1", 15 if l_leaf == 1 else 0, 15))
        tests.append(t("6. Point lookup: internal visits >= 1", 10 if l_internal >= 1 else 0, 10))
    else:
        tests.append(t("5. Point lookup: leaf visits == 1", 0, 15))
        tests.append(t("6. Point lookup: internal visits >= 1", 0, 10))

    # 7-8. Range scan
    range_stats = parse_stats_file(os.path.join(stats_dir, "range_scan.txt"))
    range_last = range_stats[-1] if range_stats else None

    if range_last is not None:
        r_internal, r_leaf, _ = range_last
        tests.append(t("7. Range scan: leaf visits >= 1", 10 if r_leaf >= 1 else 0, 10))
        tests.append(t("8. Range scan: internal visits >= 1", 10 if r_internal >= 1 else 0, 10))
    else:
        tests.append(t("7. Range scan: leaf visits >= 1", 0, 10))
        tests.append(t("8. Range scan: internal visits >= 1", 0, 10))

    # 9. Small insert
    small_stats = parse_stats_file(os.path.join(stats_dir, "insert_small.txt"))
    total_leaf_sm = sum(s[1] for s in small_stats)
    total_splits_sm = sum(s[2] for s in small_stats)

    if total_leaf_sm > 0 and total_splits_sm > 0:
        tests.append(t("9. Small insert: correct behavior", 10, 10))
    elif total_leaf_sm > 0:
        tests.append(t("9. Small insert: correct behavior", 5, 10))
    else:
        tests.append(t("9. Small insert: correct behavior", 0, 10))

    write_results(tests)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats-dir")
    parser.add_argument("--fail")
    parser.add_argument("--score", type=int, default=0)
    args = parser.parse_args()

    if args.fail:
        fail_result(args.fail, args.score)
    elif args.stats_dir:
        grade(args.stats_dir)
    else:
        fail_result("grade.py: no arguments provided")
