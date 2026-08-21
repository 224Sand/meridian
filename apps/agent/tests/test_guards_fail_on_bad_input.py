"""Every guard must be observed failing on the defect it claims to catch.

Definition of Done item 9, made automatic. It was a habit before, and habits are
what produced D-013 (a pen test that passed while the service was down) and
D-015 (a README checker that passed on a value deliberately corrupted to break
it). Both were guards that had only ever been run against a passing tree.

Each test below builds a fixture containing exactly one known defect, runs the
real guard against it, and asserts a NON-ZERO exit. A guard that passes here has
failed: it means it cannot see the thing it exists to see.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
NODE = shutil.which("node")
GIT = shutil.which("git")


def run(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    # Every argument is a literal in this file or a temp path this file created;
    # nothing here comes from input. Resolved absolute paths, not bare names.
    return subprocess.run(  # noqa: S603
        [str(NODE), str(SCRIPTS / script), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        check=False,
    )


@unittest.skipIf(NODE is None or GIT is None, "node and git are required")
class GuardsFailOnKnownBadInput(unittest.TestCase):
    def assertGuardFails(self, result: subprocess.CompletedProcess[str], expect: str) -> None:
        self.assertNotEqual(
            result.returncode,
            0,
            "the guard passed on input containing the defect it exists to catch; "
            f"stdout={result.stdout!r}",
        )
        self.assertIn(expect, result.stdout + result.stderr)

    def test_sprint_guard_catches_a_number_used_before_its_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = Path(tmp) / "docs/00-governance"
            gov.mkdir(parents=True)
            (gov / "SPRINT_00_PLAN.md").write_text("# Sprint 0\n")
            # Sprint 4 referenced, never planned.
            (Path(tmp) / "docs/NOTES.md").write_text("A defect found in Sprint 4.\n")
            self.assertGuardFails(run("check-sprints.mjs", tmp), "Sprint 4")

    def test_sprint_guard_catches_a_review_without_a_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gov = Path(tmp) / "docs/00-governance"
            gov.mkdir(parents=True)
            (gov / "SPRINT_00_PLAN.md").write_text("# Sprint 0\n")
            (gov / "SPRINT_01_REVIEW.md").write_text("# Sprint 1 review\n")
            self.assertGuardFails(run("check-sprints.mjs", tmp), "closed without being opened")

    def test_traceability_guard_catches_done_without_a_test(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            req = Path(tmp) / "docs/01-requirements"
            req.mkdir(parents=True)
            (req / "TRACEABILITY.md").write_text(
                "| ID | Need | Story | Test | Sprint | Status |\n"
                "|---|---|---|---|---|---|\n"
                "| XX-001 | a thing | S0-01 | `test_that_does_not_exist_anywhere_at_all` | 0 | Done |\n"
            )
            subprocess.run([str(GIT), "init", "-q", tmp], check=True)  # noqa: S603
            self.assertGuardFails(run("check-traceability.mjs", tmp), "XX-001")

    def test_traceability_guard_catches_a_status_outside_the_legend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            req = Path(tmp) / "docs/01-requirements"
            req.mkdir(parents=True)
            (req / "TRACEABILITY.md").write_text(
                "| ID | Need | Story | Test | Sprint | Status |\n"
                "|---|---|---|---|---|---|\n"
                "| XX-002 | a thing | S0-01 | `whatever` | 0 | Done (design) |\n"
            )
            subprocess.run([str(GIT), "init", "-q", tmp], check=True)  # noqa: S603
            self.assertGuardFails(run("check-traceability.mjs", tmp), "Done (design)")

    def test_readme_guard_catches_a_drifted_figure(self) -> None:
        """The D-015 regression, asserted rather than remembered."""
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp)
            (dst / "apps/web/src/generated").mkdir(parents=True)
            for name in ("delivery.json", "reliability.json", "architecture.json"):
                shutil.copy(
                    ROOT / "apps/web/src/generated" / name, dst / "apps/web/src/generated" / name
                )
            derived = json.loads((dst / "apps/web/src/generated/delivery.json").read_text())
            wrong = derived["defects"]["total"] + 7
            readme = (
                (ROOT / "README.md")
                .read_text()
                .replace(
                    f"| Defects logged | {derived['defects']['total']}, of which",
                    f"| Defects logged | {wrong}, of which",
                    1,
                )
            )
            (dst / "README.md").write_text(readme)
            self.assertGuardFails(run("check-readme.mjs", str(dst)), "defects")

    def test_workflow_guard_catches_a_comment_inside_a_continuation(self) -> None:
        """The D-011 regression."""
        with tempfile.TemporaryDirectory() as tmp:
            wf = Path(tmp) / ".github/workflows"
            wf.mkdir(parents=True)
            (wf / "x.yml").write_text(
                "jobs:\n"
                "  a:\n"
                "    steps:\n"
                "      - run: |\n"
                "          echo one \\\n"
                "          # this comment ends the command\n"
                "          --flag-that-becomes-a-command\n"
            )
            self.assertGuardFails(
                run("check-workflow-shell.mjs", cwd=Path(tmp)), "comment inside a backslash"
            )


if __name__ == "__main__":
    unittest.main()
