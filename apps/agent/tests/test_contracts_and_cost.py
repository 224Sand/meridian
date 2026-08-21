"""Contract and cost requirements, asserted rather than asserted-in-prose.

Two requirements in the traceability matrix carried the status `Done (design)`:
the decision had been taken and written into an ADR, but no test asserted it.
`Done (design)` is not in the matrix's own legend, and the delivery page counted
it as done, so the public number was inflated by claims nothing checked.

These are the two tests those rows named. Writing them is the honest way to
close the gap; downgrading the rows would have been the other.

AC-001 -- the experience layer is separated from the agent runtime. The value
of that split is only real if the two sides agree on the contract, and they can
drift silently because nothing imports across the boundary.

NFR-002 -- zero infrastructure cost. Now testable for the first time, because
deployment manifests exist as of Sprint 7.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import ClassVar

from sandscope_agent.api.app import RunRequest

ROOT = Path(__file__).resolve().parents[3]
BFF_ROUTE = ROOT / "apps/web/src/app/api/runs/stream/route.ts"


def _field_max(name: str) -> int:
    """The runtime's declared maximum for a request field."""
    field = RunRequest.model_fields[name]
    for meta in field.metadata:
        limit = getattr(meta, "max_length", None)
        if limit is not None:
            return int(limit)
    raise AssertionError(f"{name} declares no max_length")


class ContractBffToRuntime(unittest.TestCase):
    """AC-001. The BFF and the runtime must agree, across a process boundary."""

    def setUp(self) -> None:
        self.route = BFF_ROUTE.read_text()

    def test_bff_sends_exactly_the_fields_the_runtime_accepts(self) -> None:
        # Scope to the upstream payload. Matching field-shaped lines across the
        # whole file picked up `Authorization`, `error` and `detail` from
        # unrelated objects and failed for a reason that had nothing to do with
        # the contract -- a test failing loudly for the wrong cause is only
        # marginally better than one that cannot fail at all.
        block = re.search(r"body: JSON\.stringify\(\{(.*?)\}\),", self.route, re.DOTALL)
        self.assertIsNotNone(block, "could not locate the upstream payload in the BFF route")
        sent = set(re.findall(r"(\w+):", block.group(1)))
        accepted = set(RunRequest.model_fields)
        unknown = sent - accepted
        self.assertFalse(
            unknown,
            f"the BFF sends {sorted(unknown)}, which RunRequest does not accept; "
            "extra fields are silently dropped and the caller never learns",
        )

    def test_bff_body_ceiling_is_not_looser_than_the_runtime_accepts(self) -> None:
        """A BFF that accepts more than the runtime does forwards doomed requests.

        The caller still gets an error, so nothing is *broken* -- but it is a
        round trip, a token of rate limit and an upstream call spent to learn
        something the edge already knew. The edge bound is the cheap one.
        """
        declared = re.search(r"MAX_BODY_BYTES = (\d+) \* 1024", self.route)
        self.assertIsNotNone(declared, "the BFF declares no MAX_BODY_BYTES")
        bff_bytes = int(declared.group(1)) * 1024
        runtime_body = _field_max("body")
        # The envelope carries subject and context too, so exact equality is
        # wrong; what matters is that the edge cannot admit a body the runtime
        # will certainly refuse.
        self.assertLessEqual(
            bff_bytes,
            runtime_body + _field_max("subject") + 4096,
            f"the BFF admits {bff_bytes} bytes while the runtime caps body at "
            f"{runtime_body}; requests between the two are forwarded only to be refused",
        )


class ZeroInfrastructureCost(unittest.TestCase):
    """NFR-002. Every hosted dependency must have a free tier."""

    #: Services the project is allowed to depend on, each free at this scale.
    #: Adding a name here is a deliberate act, which is the point of the list.
    PERMITTED: ClassVar[set[str]] = {
        "huggingface.co",
        "hf.space",
        "vercel.app",
        "vercel.com",
        "neon.tech",
        "upstash.io",
        "github.com",
        "githubusercontent.com",
        "groq.com",
        "generativelanguage.googleapis.com",
        "cerebras.ai",
        "openrouter.ai",
        "mistral.ai",
        "pexels.com",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "localhost",
        "127.0.0.1",
        "example.com",
        "openapi.vercel.sh",
    }

    def _manifests(self) -> list[Path]:
        paths = [
            ROOT / "vercel.json",
            ROOT / "deploy/space/Dockerfile",
            ROOT / "deploy/space/README.md",
        ]
        paths += sorted((ROOT / ".github/workflows").glob("*.yml"))
        present = [p for p in paths if p.exists()]
        self.assertTrue(present, "no deployment manifests found to check")
        return present

    def test_no_paid_service_in_deploy_manifest(self) -> None:
        offenders: list[str] = []
        for path in self._manifests():
            for host in re.findall(r"https?://([A-Za-z0-9.-]+)", path.read_text()):
                if not any(host == ok or host.endswith("." + ok) for ok in self.PERMITTED):
                    offenders.append(f"{path.relative_to(ROOT)}: {host}")
        self.assertFalse(
            sorted(set(offenders)),
            "a host outside the free-tier allowlist appears in a deployment "
            f"manifest: {sorted(set(offenders))}",
        )

    def test_vercel_region_matches_the_data_plane(self) -> None:
        """Cross-region egress is the way a free tier stops being free."""
        config = json.loads((ROOT / "vercel.json").read_text())
        self.assertEqual(
            config.get("regions"),
            ["dub1"],
            "functions must sit beside Neon and Upstash, both in Ireland",
        )


class DeploymentClaims(unittest.TestCase):
    """INF-001 and AC-002.

    Both rows claimed Done while naming tests that did not exist. Neither was
    dishonest exactly -- the decision really had been taken, the gate really
    did run -- but "Done" in this matrix means a test is green, and no test was.
    They are writable now that the deployment manifests exist, so they are
    written rather than downgraded.
    """

    def test_container_binds_7860(self) -> None:
        """INF-001. Spaces routes to one port; binding another serves nothing."""
        dockerfile = (ROOT / "deploy/space/Dockerfile").read_text()
        self.assertIn("EXPOSE 7860", dockerfile)
        self.assertRegex(
            dockerfile,
            r"--port \$\{PORT:-7860\}",
            "the container must listen on 7860 by default",
        )
        self.assertRegex(
            dockerfile,
            r"--host 0\.0\.0\.0",
            "binding to 127.0.0.1 inside a container is unreachable from outside it",
        )
        readme = (ROOT / "deploy/space/README.md").read_text()
        self.assertIn(
            "app_port: 7860",
            readme,
            "the Space manifest must declare the same port the container binds",
        )

    def test_delivery_reads_live_github(self) -> None:
        """AC-002. The delivery page must not hand-write its own CI status.

        The whole claim of that page is that its numbers can be checked. A
        stored pass/fail would be the one number on it that could quietly become
        a lie.
        """
        route = (ROOT / "apps/web/src/app/api/ci/route.ts").read_text()
        self.assertIn(
            "https://api.github.com/repos/",
            route,
            "CI status must come from the GitHub API, not from a committed value",
        )
        component = (ROOT / "apps/web/src/components/CiStatus.tsx").read_text()
        self.assertIn(
            'fetch("/api/ci")',
            component,
            "the component must read the live route rather than import a fixture",
        )
        self.assertNotIn(
            "generated/ci.json",
            component,
            "a build-time snapshot would go stale the moment the next push ran",
        )


if __name__ == "__main__":
    unittest.main()
