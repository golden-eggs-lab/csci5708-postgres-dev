#!/usr/bin/env python3
"""
Gradescope Autograder — grade.py
CSCI 5708 Lab 3: DML Operation Logging
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


# Regex patterns for each DML log type
INSERT_RE = re.compile(r"DML_LAB_LOG:\s*INSERT\s+val=(-?\d+)")
DELETE_RE = re.compile(r"DML_LAB_LOG:\s*DELETE\s+val=(-?\d+)")
UPDATE_RE = re.compile(r"DML_LAB_LOG:\s*UPDATE\s+old_val=(-?\d+)\s+new_val=(-?\d+)")


def parse_log_file(path):
    """Parse a stderr log file and return lists of captured values."""
    inserts = []
    deletes = []
    updates = []
    if not os.path.exists(path):
        return inserts, deletes, updates
    with open(path) as f:
        for line in f:
            m = INSERT_RE.search(line)
            if m:
                inserts.append(int(m.group(1)))
            m = DELETE_RE.search(line)
            if m:
                deletes.append(int(m.group(1)))
            m = UPDATE_RE.search(line)
            if m:
                updates.append((int(m.group(1)), int(m.group(2))))
    return inserts, deletes, updates


def t(name, score, max_score):
    return {"name": name, "score": score, "max_score": max_score}


def grade(stats_dir):
    tests = []

    # 1. Compilation (10 pts) — if we got here, it compiled
    tests.append(t("1. Compilation", 10, 10))

    # ---------------------------------------------------------------
    # 2. INSERT correctness (20 pts)
    # ---------------------------------------------------------------
    ins_on, _, _ = parse_log_file(os.path.join(stats_dir, "insert_on.txt"))
    ins_off, _, _ = parse_log_file(os.path.join(stats_dir, "insert_off.txt"))

    # Expected: odd values 11, 13, 15 logged; even values 12, 14, 16 NOT
    insert_logged_odds = set(ins_on) & {11, 13, 15}
    insert_logged_evens = set(ins_on) & {12, 14, 16}

    # Part a: correct odd values logged (10 pts)
    if len(insert_logged_odds) == 3 and len(insert_logged_evens) == 0:
        tests.append(t("2a. INSERT: correct values logged", 10, 10))
    elif len(insert_logged_odds) >= 1:
        tests.append(t("2a. INSERT: correct values logged", 5, 10))
    else:
        tests.append(t("2a. INSERT: correct values logged", 0, 10))

    # Part b: logging off produces no output (5 pts)
    if len(ins_off) == 0:
        tests.append(t("2b. INSERT: logging OFF produces no output", 5, 5))
    else:
        tests.append(t("2b. INSERT: logging OFF produces no output", 0, 5))

    # Part c: output format correct (5 pts)
    # Check that at least one line matches the exact pattern
    format_ok = len(ins_on) > 0  # parser found valid formatted lines
    tests.append(t("2c. INSERT: output format", 5 if format_ok else 0, 5))

    # ---------------------------------------------------------------
    # 3. DELETE correctness (30 pts)
    # ---------------------------------------------------------------
    _, del_on, _ = parse_log_file(os.path.join(stats_dir, "delete_on.txt"))
    _, del_off, _ = parse_log_file(os.path.join(stats_dir, "delete_off.txt"))

    # Expected: even values 2, 4 logged; odd values 1, 3 NOT
    delete_logged_evens = set(del_on) & {2, 4}
    delete_logged_odds = set(del_on) & {1, 3}

    # Part a: correct even values logged (15 pts)
    if len(delete_logged_evens) == 2 and len(delete_logged_odds) == 0:
        tests.append(t("3a. DELETE: correct values logged", 15, 15))
    elif len(delete_logged_evens) >= 1:
        tests.append(t("3a. DELETE: correct values logged", 7, 15))
    else:
        tests.append(t("3a. DELETE: correct values logged", 0, 15))

    # Part b: logging off produces no output (5 pts)
    if len(del_off) == 0:
        tests.append(t("3b. DELETE: logging OFF produces no output", 5, 5))
    else:
        tests.append(t("3b. DELETE: logging OFF produces no output", 0, 5))

    # Part c: old tuple fetched correctly (10 pts)
    # Verify that the values in the log match what was actually in the table
    # (the fact that correct values appeared means fetch worked)
    if len(delete_logged_evens) == 2:
        tests.append(t("3c. DELETE: old tuple fetch correct", 10, 10))
    elif len(delete_logged_evens) >= 1:
        tests.append(t("3c. DELETE: old tuple fetch correct", 5, 10))
    else:
        tests.append(t("3c. DELETE: old tuple fetch correct", 0, 10))

    # ---------------------------------------------------------------
    # 4. UPDATE correctness (30 pts)
    # ---------------------------------------------------------------
    _, _, upd_on = parse_log_file(os.path.join(stats_dir, "update_on.txt"))
    _, _, upd_off = parse_log_file(os.path.join(stats_dir, "update_off.txt"))

    # Test E inserts:
    #   UPDATE t_lab3 SET id = 100 WHERE id = 9;   old=9(div3) new=100  -> should log
    #   UPDATE t_lab3 SET id = 200 WHERE id = 7;   old=7       new=200  -> should NOT
    #   UPDATE t_lab3 SET id = 300 WHERE id = 8;   old=8       new=300(div3) -> should log
    #   UPDATE t_lab3 SET id = 21 WHERE id = 10;   old=10      new=21(div3) -> should log

    expected_updates = {(9, 100), (8, 300), (10, 21)}
    unexpected_update = (7, 200)

    upd_set = set(upd_on)
    correct_logged = upd_set & expected_updates
    wrong_logged = unexpected_update in upd_set

    # Part a: correct updates logged (15 pts)
    if len(correct_logged) == 3 and not wrong_logged:
        tests.append(t("4a. UPDATE: correct values logged", 15, 15))
    elif len(correct_logged) >= 1:
        score = 5 if wrong_logged else 10
        tests.append(t("4a. UPDATE: correct values logged", score, 15))
    else:
        tests.append(t("4a. UPDATE: correct values logged", 0, 15))

    # Part b: logging off produces no output (5 pts)
    if len(upd_off) == 0:
        tests.append(t("4b. UPDATE: logging OFF produces no output", 5, 5))
    else:
        tests.append(t("4b. UPDATE: logging OFF produces no output", 0, 5))

    # Part c: old and new values both correct (10 pts)
    # Check that old_val and new_val pairs match expected
    if len(correct_logged) == 3:
        tests.append(t("4c. UPDATE: old/new values correct", 10, 10))
    elif len(correct_logged) >= 1:
        tests.append(t("4c. UPDATE: old/new values correct", 5, 10))
    else:
        tests.append(t("4c. UPDATE: old/new values correct", 0, 10))

    # ---------------------------------------------------------------
    # 5. GUC registration (10 pts)
    # ---------------------------------------------------------------
    # If INSERT worked with SET, the GUC must be registered
    guc_works = len(ins_on) > 0 or len(del_on) > 0 or len(upd_on) > 0
    tests.append(t("5. GUC registered and functional", 10 if guc_works else 0, 10))

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
