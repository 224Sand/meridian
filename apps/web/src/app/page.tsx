import Link from "next/link";

import config from "../../../../product.config.json";

/**
 * Landing surface.
 *
 * Sprint 5 makes it correct and legible; Sprint 6 makes it meet DR-001 with
 * scroll-driven scenes and footage. Building both at once produces a
 * half-finished version of each, which R-05 exists to prevent.
 *
 * Every claim here is one the system can be made to demonstrate on /console.
 */

const SCENES = [
  {
    kicker: "The problem",
    heading: "Nobody can answer the four questions",
    body: "Teams are putting agents in front of production operations. When it matters, four questions decide whether it ships — is it grounded, is it safe, what did it cost, and what did it actually do. Most deployments cannot answer any of them with evidence.",
  },
  {
    kicker: "Grounding",
    heading: "Every claim points at a passage",
    body: "Citations attach to sentences, not to responses. A model that puts one marker at the end of six sentences has cited one and asserted five. A marker pointing outside the evidence is recorded as unresolved rather than dropped — a fabricated citation looks like grounding, so it has to survive where a check can see it.",
  },
  {
    kicker: "Refusal",
    heading: "It says when it does not know",
    body: "Refusal is gated on a signal measured to separate answerable from unanswerable, not on a score that reads the same for both. Thresholds come from error budgets against 715 labelled questions. The false-answer rate is 4.7% and the interval is published.",
  },
  {
    kicker: "Determinism",
    heading: "Routing is a decision, not luck",
    body: "Providers are attempted in a fixed order. A rate limit disables one for a bounded window; an exhausted quota disables it for the process. Two identical requests take the same path, which is what makes a trace worth reading.",
  },
  {
    kicker: "Governance",
    heading: "A risky action stops for a human",
    body: "The approval node has no edge back into the graph. Reaching it ends the run, and a decision starts a new one carrying the record. It is enforced by topology rather than by care, because an approval step that can auto-proceed is a control that consumes attention and provides nothing.",
  },
  {
    kicker: "Economics",
    heading: "Cost is bounded before it is incurred",
    body: "No live model call happens without an open budget. Every call is priced at worst case before it fires and reconciled after. Pricing after the fact is accounting; pricing before is control.",
  },
] as const;

export default function Home() {
  return (
    <main>
      <section
        className="wrap"
        style={{ minHeight: "88vh", display: "flex", flexDirection: "column", justifyContent: "center", paddingBlock: "var(--s9)" }}
      >
        <p className="mono rise" style={{ color: "var(--text-3)", marginBottom: "var(--s5)" }}>
          {config.wordmark}
        </p>
        <h1 className="rise" style={{ animationDelay: "60ms", marginBottom: "var(--s6)" }}>
          The control plane for AI agents that operate production systems.
        </h1>
        <p className="rise" style={{ animationDelay: "120ms", color: "var(--text-2)", fontSize: "1.25rem", marginBottom: "var(--s7)" }}>
          Every action routed deterministically, grounded with citations, evaluated,
          traced, priced, and gated on human approval when it crosses a risk line.
        </p>
        <div className="rise" style={{ animationDelay: "180ms", display: "flex", gap: "var(--s3)", flexWrap: "wrap" }}>
          <Link
            href="/console"
            style={{
              background: "var(--accent)", color: "#001", padding: "var(--s3) var(--s5)",
              borderRadius: 8, fontWeight: 500,
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
      </section>

      {SCENES.map((scene) => (
        <section key={scene.kicker} className="wrap" style={{ paddingBlock: "var(--s9)", borderTop: "1px solid var(--line)" }}>
          <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s4)" }}>
            {scene.kicker.toUpperCase()}
          </p>
          <h2 style={{ marginBottom: "var(--s5)", maxWidth: "20ch" }}>{scene.heading}</h2>
          <p style={{ color: "var(--text-2)", fontSize: "1.125rem" }}>{scene.body}</p>
        </section>
      ))}

      <section className="wrap" style={{ paddingBlock: "var(--s9)", borderTop: "1px solid var(--line)" }}>
        <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s4)" }}>
          A NOTE ON WHAT THIS IS
        </p>
        <p style={{ color: "var(--text-2)" }}>
          {config.name} is a demonstration product built to production standards on
          synthetic data. The engineering is real — the services, the failover, the
          retrieval, the evaluation, the tests, the pipeline. The customers are
          simulated, and saying so is cheaper than being found out.
        </p>
      </section>
    </main>
  );
}
