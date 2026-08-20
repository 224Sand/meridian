"""Run both golden suites and write the report (FR-015, FR-016).

    python training/run_evaluation.py

Exit code is 1 only if `core` fails. `probe` warnings never fail the build: a
suite that could block would be tuned until it stopped complaining, and the
limitations it records would leave the report without being fixed.
"""

from __future__ import annotations

import os
import subprocess
import sys

from sandscope_agent.evaluation.harness import run_core, run_probe, write_report


def git_sha() -> str:
    if sha := os.environ.get("GITHUB_SHA"):
        return sha
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    core, probe = run_core(), run_probe()

    for result in (core, probe):
        header = f"golden/{result.suite}"
        status = "PASS" if result.passed else "FAIL"
        if result.warned:
            status += "  (warnings expected)"
        print(f"\n=== {header}: {status} ===")
        for check in result.checks:
            mark = "ok  " if check.passed else ("WARN" if result.suite == "probe" else "FAIL")
            print(f"  [{mark}] {check.name}")
            print(f"         {check.detail}")

    path = write_report([core, probe], git_sha=git_sha())
    print(f"\nreport written to {path}")

    if not core.passed:
        print("\ngolden/core FAILED - blocking")
        return 1
    if probe.warned:
        print("\ngolden/probe warned, which is expected. A CHANGE in its result")
        print("requires a written explanation at the sprint review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
