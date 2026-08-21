import Link from "next/link";

import {
  Approval, Budget, CitedClaim, Failover, Refusal, Waterfall,
} from "@/components/Artifact";
import Scene from "@/components/Scene";
import ScrollScrubbed from "@/components/ScrollScrubbed";
import config from "@/generated/product.config.json";

/**
 * The landing surface (DR-001).
 *
 * The transferable part of the reference standard is not the look: motion is
 * scroll-driven so the reader sets the pace, one idea occupies one viewport,
 * and type carries hierarchy so colour can carry meaning.
 *
 * Every scene's hero is something the system actually produced. Footage is
 * atmosphere in one place and never the subject.
 */

export default function Home() {
  return (
    <main>
      <ScrollScrubbed src="/media/hero.mp4" poster="/media/hero.jpg">
        <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s5)" }}>
          {config.wordmark}
        </p>
        <h1 style={{ marginBottom: "var(--s6)", maxWidth: "16ch" }}>
          Agents that touch production should be as accountable as the people who do.
        </h1>
        <p style={{ color: "var(--text-2)", fontSize: "1.25rem", marginBottom: "var(--s7)" }}>
          Every action routed deterministically, grounded with citations, evaluated,
          traced, priced, and gated on human approval when it crosses a risk line.
        </p>
        <div style={{ display: "flex", gap: "var(--s3)", flexWrap: "wrap" }}>
          <Link
            href="/console"
            style={{
              background: "var(--accent)", color: "#001",
              padding: "var(--s3) var(--s5)", borderRadius: 8, fontWeight: 500,
            }}
          >
            Watch it run
          </Link>
          <a
            href={`https://github.com/${config.repo}`}
            style={{
              border: "1px solid var(--line)", color: "var(--text)",
              padding: "var(--s3) var(--s5)", borderRadius: 8,
            }}
          >
            Read the source
          </a>
        </div>
      </ScrollScrubbed>

      <Scene
        kicker="The problem"
        heading="Four questions decide whether it ships"
        body="Teams are putting agents in front of production operations. When it matters, four questions decide whether it goes live — is it grounded, is it safe, what did it cost, and what did it actually do. Most deployments cannot answer any of them with evidence, so the agent either ships unaccountably or does not ship."
      />

      <Scene
        kicker="Grounding"
        heading="Every claim points at a passage"
        body="Citations attach to sentences, not to responses. A model that puts one marker at the end of six sentences has cited one and asserted five. A marker pointing outside the evidence is recorded as unresolved rather than dropped — a fabricated citation looks exactly like grounding, so it has to survive where a check can see it."
        aside={<CitedClaim />}
      />

      <Scene
        kicker="Refusal"
        heading="It says when it does not know"
        body="Refusal is gated on signals measured to separate answerable from unanswerable, not on a score that reads the same for both. Thresholds come from explicit error budgets against 715 labelled questions whose labels are true by construction rather than assigned by a model."
        aside={<Refusal />}
      />

      <Scene
        kicker="Determinism"
        heading="Routing is a decision, not luck"
        body="Providers are attempted in a fixed order. Two identical requests take the same path, which is what makes a trace worth reading and a failure worth reproducing. Nothing here reads a module global or the wall clock."
        aside={<Failover />}
      />

      <Scene
        kicker="Cost"
        heading="Most of the work costs nothing"
        body="If a typed rule can decide it, no token is spent. Five of seven nodes in a typical run are deterministic and take 13 milliseconds between them, against 14 seconds for the two model calls. The governance layer is close to free — which is the argument for deciding as much as possible without a model, stated as a number."
        aside={<Waterfall />}
      />

      <Scene
        kicker="Governance"
        heading="A risky action stops for a human"
        body="The approval node has no edge back into the graph. Reaching it ends the run, and a decision starts a new one carrying the record. It is enforced by topology rather than by care, because an approval step that can auto-proceed consumes a reviewer's attention and protects nothing."
        aside={<Approval />}
      />

      <Scene
        kicker="Economics"
        heading="Cost is bounded before it is incurred"
        body="No live model call happens without an open budget. Every call is priced at worst case before it fires and reconciled after. Pricing after the fact is accounting; pricing before is control."
        aside={<Budget />}
      />

      <section className="wrap" style={{ paddingBlock: "var(--s9)", borderTop: "1px solid var(--line)" }}>
        <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s4)" }}>
          A NOTE ON WHAT THIS IS
        </p>
        <p style={{ color: "var(--text-2)", marginBottom: "var(--s5)" }}>
          {config.name} is a demonstration product built to production standards on
          synthetic data. The engineering is real — the services, the failover, the
          retrieval, the evaluation, the pipeline. The customers are simulated, and
          saying so is cheaper than being found out.
        </p>
        <p style={{ color: "var(--text-3)", fontSize: "0.9375rem" }}>
          Every number on this page is measured and reproducible from the repository.
          Ten defects found during the build are published, including the six that only
          appeared once the assembled system was actually run.
        </p>
      </section>
    </main>
  );
}
