#!/usr/bin/env python3
"""
Gradescope Autograder — grade.py
CSCI 5708 Lab: 2nd-LRU Buffer Replacement

Parses the PostgreSQL server stdout to extract "Candidate buffers:" and
"Replaced buffer:" line pairs, then verifies the 2nd-LRU algorithm
correctness.

Grading rubric:
  - Compilation:           5 pts  (pass/fail — handled by run_autograder)
  - SQL execution:         5 pts  (COPY 10000 succeeded)
  - Output format:         5 pts  (lines are well-formed and parseable)
  - Correctness:           85 pts  (replaced buffer = 2nd-smallest timestamp)
  Total:                  100 pts
"""

import argparse
import json
import re
import sys
import os

RESULTS_PATH = os.environ.get("RESULTS_PATH", "/autograder/results/results.json")

# ── Scoring weights ──────────────────────────────────────────────────────────
SCORE_COMPILATION   = 5
SCORE_SQL_EXECUTION = 5
SCORE_FORMAT        = 5
SCORE_CORRECTNESS   = 85
TOTAL               = SCORE_COMPILATION + SCORE_SQL_EXECUTION + SCORE_FORMAT + SCORE_CORRECTNESS


def write_results(results: dict):
    """Write results.json for Gradescope."""
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)


def fail_result(message: str, score: float = 0):
    """Write a single-test failure result and exit."""
    results = {
        "score": score,
        "output": message,
        "output_format": "md",
        "stdout_visibility": "visible",
        "tests": [
            {
                "name": "Autograder Error",
                "score": score,
                "max_score": TOTAL,
                "output": message,
                "output_format": "md",
                "visibility": "visible",
            }
        ],
    }
    write_results(results)
    sys.exit(0)


def parse_candidate_line(line: str):
    """
    Parse a line like: "Candidate buffers: 1, 56, 59, 55"
    Returns a list of ints, or None on parse failure.
    """
    prefix = "Candidate buffers: "
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):].strip()
    if not rest:
        return None
    try:
        timestamps = [int(x.strip()) for x in rest.split(",")]
    except ValueError:
        return None
    return timestamps


def parse_replaced_line(line: str):
    """
    Parse a line like: "Replaced buffer: 39"
    Returns an int, or None on parse failure.
    """
    prefix = "Replaced buffer: "
    if not line.startswith(prefix):
        return None
    rest = line[len(prefix):].strip()
    try:
        return int(rest)
    except ValueError:
        return None


def second_smallest(values: list):
    """
    Given a list of ints, return the second-smallest value.
    If only one value, return that value.
    """
    if len(values) == 0:
        return None
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    return sorted_vals[1]


def grade_output(stdout_lines: list):
    """
    Parse and grade the server stdout.

    Returns:
        (format_score, correctness_score, total_pairs, format_errors, logic_errors, details)
    """
    # Extract only the relevant lines
    candidate_lines = []
    replaced_lines = []
    all_relevant = []

    for line in stdout_lines:
        stripped = line.strip()
        if stripped.startswith("Candidate buffers:"):
            candidate_lines.append(stripped)
            all_relevant.append(("candidate", stripped))
        elif stripped.startswith("Replaced buffer:"):
            replaced_lines.append(stripped)
            all_relevant.append(("replaced", stripped))

    # Pair them up: each "Candidate buffers:" should be followed by "Replaced buffer:"
    pairs = []
    i = 0
    while i < len(all_relevant):
        if all_relevant[i][0] == "candidate":
            if i + 1 < len(all_relevant) and all_relevant[i + 1][0] == "replaced":
                pairs.append((all_relevant[i][1], all_relevant[i + 1][1]))
                i += 2
            else:
                # Candidate without a matching replaced line
                pairs.append((all_relevant[i][1], None))
                i += 1
        else:
            # Replaced without a preceding candidate
            pairs.append((None, all_relevant[i][1]))
            i += 1

    total_pairs = len(pairs)
    format_errors = []
    logic_errors = []
    correct_count = 0

    for idx, (cand_line, repl_line) in enumerate(pairs):
        pair_num = idx + 1

        # ── Format check ──
        if cand_line is None:
            format_errors.append(f"Pair {pair_num}: Missing 'Candidate buffers:' line before 'Replaced buffer:' line.")
            continue
        if repl_line is None:
            format_errors.append(f"Pair {pair_num}: Missing 'Replaced buffer:' line after 'Candidate buffers:' line.")
            continue

        candidates = parse_candidate_line(cand_line)
        if candidates is None:
            format_errors.append(
                f"Pair {pair_num}: Could not parse candidate line.\n"
                f"  Got: `{cand_line}`\n"
                f"  Expected format: `Candidate buffers: T1, T2, T3, ...`"
            )
            continue

        replaced = parse_replaced_line(repl_line)
        if replaced is None:
            format_errors.append(
                f"Pair {pair_num}: Could not parse replaced line.\n"
                f"  Got: `{repl_line}`\n"
                f"  Expected format: `Replaced buffer: T`"
            )
            continue

        # ── Format validation: check exact format ──
        # Rebuild expected candidate line and compare
        expected_cand = "Candidate buffers: " + ", ".join(str(t) for t in candidates)
        if cand_line != expected_cand:
            format_errors.append(
                f"Pair {pair_num}: Candidate line has formatting issues.\n"
                f"  Got:      `{cand_line}`\n"
                f"  Expected: `{expected_cand}`"
            )

        expected_repl = f"Replaced buffer: {replaced}"
        if repl_line != expected_repl:
            format_errors.append(
                f"Pair {pair_num}: Replaced line has formatting issues.\n"
                f"  Got:      `{repl_line}`\n"
                f"  Expected: `{expected_repl}`"
            )

        # ── Correctness check ──
        if replaced not in candidates:
            logic_errors.append(
                f"Pair {pair_num}: Replaced timestamp {replaced} is not in the candidate list."
            )
            continue

        expected_victim = second_smallest(candidates)
        if replaced == expected_victim:
            correct_count += 1
        else:
            logic_errors.append(
                f"Pair {pair_num}: Expected 2nd-smallest = {expected_victim}, "
                f"but got Replaced buffer = {replaced}.\n"
                f"  Candidates: {candidates}"
            )

    # ── Scoring ──
    if total_pairs == 0:
        format_score = 0.0
        correctness_score = 0.0
    else:
        # Format: fraction of pairs that parsed successfully
        parseable_pairs = total_pairs - len(format_errors)
        format_score = max(0.0, (parseable_pairs / total_pairs)) * SCORE_FORMAT

        # Correctness: fraction of pairs where 2nd-LRU logic is correct
        if parseable_pairs > 0:
            correctness_score = (correct_count / parseable_pairs) * SCORE_CORRECTNESS
        else:
            correctness_score = 0.0

    return (
        round(format_score, 2),
        round(correctness_score, 2),
        total_pairs,
        format_errors,
        logic_errors,
        correct_count,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fail", type=str, default=None,
                        help="If set, write a failure message and exit.")
    parser.add_argument("--score", type=float, default=0,
                        help="Score to assign on failure.")
    parser.add_argument("--stdout-file", type=str, default=None,
                        help="Path to server stdout log file.")
    parser.add_argument("--sql-output", type=str, default="",
                        help="The psql output from the test run.")
    args = parser.parse_args()

    # ── Handle explicit failure (called from run_autograder) ──
    if args.fail:
        fail_result(args.fail, args.score)

    # ── Test 1: Compilation (if we got here, compilation passed) ──
    compilation_score = SCORE_COMPILATION
    compilation_status = "passed"

    # ── Test 2: SQL execution ──
    sql_score = 0
    sql_status = "failed"
    sql_output_msg = args.sql_output

    if "COPY 10000" in args.sql_output:
        sql_score = SCORE_SQL_EXECUTION
        sql_status = "passed"
        sql_output_msg = "Test SQL executed successfully: 10,000 rows loaded."
    else:
        sql_output_msg = (
            f"Test SQL did not complete successfully.\n\n"
            f"Expected to see `COPY 10000` in the output.\n\n"
            f"Actual output:\n```\n{args.sql_output}\n```"
        )

    # ── Read server stdout ──
    stdout_lines = []
    if args.stdout_file and os.path.isfile(args.stdout_file):
        with open(args.stdout_file, "r", errors="replace") as f:
            stdout_lines = f.readlines()

    # ── Test 3 & 4: Format + Correctness ──
    if not stdout_lines or sql_score == 0:
        format_score = 0
        correctness_score = 0
        total_pairs = 0
        format_errors = []
        logic_errors = []
        correct_count = 0

        if sql_score == 0:
            no_output_reason = "SQL execution failed, so no replacement output was produced."
        else:
            no_output_reason = (
                "No `Candidate buffers:` / `Replaced buffer:` output was found in server stdout.\n\n"
                "Possible causes:\n"
                "- You did not add `printf` statements in your 2nd-LRU implementation.\n"
                "- Your code never reached the 2nd-LRU path (all buffers came from freelist).\n"
                "- `printf` output was sent to stderr instead of stdout."
            )
    else:
        (
            format_score,
            correctness_score,
            total_pairs,
            format_errors,
            logic_errors,
            correct_count,
        ) = grade_output(stdout_lines)

        no_output_reason = None

    # ── Build test results ──
    tests = []

    # Test 1: Compilation
    tests.append({
        "name": "1. Compilation",
        "score": compilation_score,
        "max_score": SCORE_COMPILATION,
        "status": compilation_status,
        "output": "Your `freelist.c` compiled successfully with PostgreSQL.",
        "visibility": "visible",
    })

    # Test 2: SQL execution
    tests.append({
        "name": "2. SQL Execution (COPY 10000)",
        "score": sql_score,
        "max_score": SCORE_SQL_EXECUTION,
        "status": sql_status,
        "output": sql_output_msg,
        "output_format": "md",
        "visibility": "visible",
    })

    # Test 3: Output format
    if no_output_reason:
        format_detail = no_output_reason
    elif total_pairs == 0:
        format_detail = (
            "No `Candidate buffers:` / `Replaced buffer:` line pairs found.\n\n"
            "Make sure your implementation prints output using the exact format specified in the lab document."
        )
    else:
        parseable = total_pairs - len(format_errors)
        format_detail = f"**{parseable} / {total_pairs}** line pairs parsed successfully.\n\n"
        if format_errors:
            format_detail += f"**Format errors ({len(format_errors)}):**\n\n"
            for err in format_errors[:10]:  # show first 10
                format_detail += f"- {err}\n"
            if len(format_errors) > 10:
                format_detail += f"\n... and {len(format_errors) - 10} more format errors.\n"
        else:
            format_detail += "All line pairs are correctly formatted."

    tests.append({
        "name": "3. Output Format",
        "score": format_score,
        "max_score": SCORE_FORMAT,
        "status": "passed" if format_score == SCORE_FORMAT else "failed",
        "output": format_detail,
        "output_format": "md",
        "visibility": "visible",
    })

    # Test 4: Correctness
    if no_output_reason:
        correctness_detail = no_output_reason
    elif total_pairs == 0:
        correctness_detail = "No output to verify."
    else:
        parseable = total_pairs - len(format_errors)
        correctness_detail = f"**{correct_count} / {parseable}** replacements used the correct 2nd-LRU victim.\n\n"
        if logic_errors:
            correctness_detail += f"**Logic errors ({len(logic_errors)}):**\n\n"
            for err in logic_errors[:10]:  # show first 10
                correctness_detail += f"- {err}\n"
            if len(logic_errors) > 10:
                correctness_detail += f"\n... and {len(logic_errors) - 10} more logic errors.\n"
        else:
            correctness_detail += "All replacements are correct!"

    tests.append({
        "name": "4. 2nd-LRU Correctness",
        "score": correctness_score,
        "max_score": SCORE_CORRECTNESS,
        "status": "passed" if correctness_score == SCORE_CORRECTNESS else "failed",
        "output": correctness_detail,
        "output_format": "md",
        "visibility": "visible",
    })

    # ── Summary ──
    total_score = round(compilation_score + sql_score + format_score + correctness_score, 2)

    summary = f"**Total: {total_score} / {TOTAL}**\n\n"
    if total_pairs > 0:
        summary += f"- Replacement pairs found: {total_pairs}\n"
        summary += f"- Format errors: {len(format_errors)}\n"
        summary += f"- Logic errors: {len(logic_errors)}\n"
        summary += f"- Correct replacements: {correct_count}\n"

    results = {
        "score": total_score,
        "output": summary,
        "output_format": "md",
        "stdout_visibility": "hidden",
        "tests": tests,
    }

    write_results(results)
    print(f"Grading complete. Score: {total_score}/{TOTAL}")


if __name__ == "__main__":
    main()
