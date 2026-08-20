"use client";

/**
 * The console. A visitor triggers a run and watches the agent reason.
 *
 * Built against the acceptance criteria in
 * docs/01-requirements/ACCEPTANCE_CRITERIA_CONSOLE.md, which were written
 * before this file existed so that acceptance is judged against criteria rather
 * than against whatever got built.
 */

import { useCallback, useRef, useState } from "react";

import { readEvents, type Citation, type NodeEvent, type RunCompleted } from "@/lib/events";

const PRESETS = [
  {
    id: "pool",
    label: "Connection pool exhaustion",
    workload: "incident_triage",
    subject: "inc-4471",
    body: "db.pool.wait_ms is climbing on orders-db and available connections reached zero",
    context: { service: "orders-db", tier: "0", signature: "db.pool.saturated" },
  },
  {
    id: "cert",
    label: "TLS certificate expiry",
    workload: "incident_triage",
    subject: "inc-4472",
    body: "tls.handshake_failures_per_s went from zero to full rate in one sample interval on edge-gateway",
    context: { service: "edge-gateway", tier: "0", signature: "tls.handshake.failure" },
  },
  {
    id: "change",
    label: "Change review — raise a pool ceiling",
    workload: "change_review",
    subject: "chg-881",
    body: "raise the orders-db connection pool ceiling from 100 to 200 to absorb peak traffic",
    context: { service: "orders-db", tier: "0", change_kind: "configuration" },
  },
  {
    id: "gap",
    label: "Something the corpus cannot answer",
    workload: "incident_triage",
    subject: "inc-4473",
    body: "what is the disaster recovery failover procedure for a full region loss",
    context: {},
  },
] as const;

type Phase = "idle" | "running" | "done";

const NODE_LABEL: Record<string, string> = {
  classify: "Classify",
  retrieve: "Retrieve evidence",
  assess_evidence: "Assess evidence",
  adjudicate: "Adjudicate",
  hypothesise: "Reason",
  verify: "Verify citations",
  propose_action: "Propose action",
  risk_gate: "Risk gate",
  refuse: "Refuse",
  escalate: "Escalate",
  await_approval: "Await approval",
  emit: "Emit",
};

function verdictChip(verdict?: string) {
  if (verdict === "sufficient") return <span className="chip chip--grounded">evidence sufficient</span>;
  if (verdict === "insufficient") return <span className="chip chip--refused">evidence insufficient</span>;
  if (verdict === "ambiguous") return <span className="chip chip--refused">ambiguous — adjudicating</span>;
  return null;
}

function riskChip(risk?: string | null) {
  if (!risk) return null;
  const blocked = risk === "high" || risk === "critical";
  return (
    <span className={`chip ${blocked ? "chip--blocked" : "chip--neutral"}`}>
      risk: {risk}{blocked ? " — approval required" : ""}
    </span>
  );
}

export default function Console() {
  const [preset, setPreset] = useState<(typeof PRESETS)[number]>(PRESETS[0]!);
  const [phase, setPhase] = useState<Phase>("idle");
  const [events, setEvents] = useState<NodeEvent[]>([]);
  const [result, setResult] = useState<RunCompleted | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openCitation, setOpenCitation] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const start = useCallback(async () => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;

    setPhase("running");
    setEvents([]);
    setResult(null);
    setError(null);

    try {
      const response = await fetch("/api/runs/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workload: preset.workload,
          subject: preset.subject,
          body: preset.body,
          context: preset.context,
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => ({ error: "unknown" }));
        setError(
          detail.error === "runtime_unreachable"
            ? "The agent runtime is asleep or unreachable. It sleeps after prolonged inactivity on the free tier."
            : detail.error === "limiter_unavailable"
              ? "The rate limiter is unreachable, and this endpoint fails closed by design."
              : `${detail.error}: ${detail.detail ?? ""}`,
        );
        setPhase("done");
        return;
      }

      for await (const event of readEvents(response)) {
        if (event.kind === "node_completed") setEvents((prior) => [...prior, event.data]);
        else if (event.kind === "run_completed") setResult(event.data);
        else if (event.kind === "error") setError(`${event.data.error}: ${event.data.detail}`);
      }
      setPhase("done");
    } catch (caught) {
      if ((caught as Error)?.name !== "AbortError") {
        setError(caught instanceof Error ? caught.message : "unknown failure");
      }
      setPhase("done");
    }
  }, [preset]);

  const terminal = events.find((e) =>
    ["refuse", "escalate", "await_approval", "emit"].includes(e.node),
  );
  const outcome = terminal?.node;
  /**
   * An escalated or refused run produced no accepted answer.
   *
   * The first version rendered the last hypothesis regardless of outcome, so a
   * run the system REFUSED to emit was displayed as though it had been
   * accepted - which contradicts the product's central claim in the one place a
   * visitor would look. The draft is still shown, because hiding it would be
   * worse, but it is labelled as rejected and the uncited claims are named.
   */
  const rejected = outcome === "escalate" || outcome === "refuse";
  const assessment = [...events].reverse().find((e) => e.node === "hypothesise")?.text;
  const uncited = [...events].reverse().find((e) => e.node === "verify")?.uncited ?? [];
  const citations: Citation[] = [...events].reverse().find((e) => e.node === "verify")?.citations ?? [];
  const proposal = events.find((e) => e.node === "propose_action")?.proposal;
  const risk = events.find((e) => e.node === "risk_gate");
  const evidence = events.find((e) => e.node === "assess_evidence");
  const retrieval = events.find((e) => e.node === "retrieve");

  return (
    <div style={{ display: "grid", gap: "var(--s5)" }}>
      <section className="panel">
        <h3 style={{ marginBottom: "var(--s4)" }}>Choose a scenario</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--s2)", marginBottom: "var(--s4)" }}>
          {PRESETS.map((option) => (
            <button
              key={option.id}
              onClick={() => setPreset(option)}
              aria-pressed={preset.id === option.id}
              style={{
                borderColor: preset.id === option.id ? "var(--accent)" : "var(--line)",
                color: preset.id === option.id ? "var(--text)" : "var(--text-2)",
              }}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="mono" style={{ color: "var(--text-2)", marginBottom: "var(--s4)" }}>
          {preset.body}
        </p>
        <button
          onClick={start}
          disabled={phase === "running"}
          style={{ background: "var(--accent)", borderColor: "var(--accent)", color: "#001" }}
        >
          {phase === "running" ? "Running…" : "Run triage"}
        </button>
      </section>

      {error && (
        <section className="panel" style={{ borderColor: "var(--blocked)" }}>
          <span className="chip chip--blocked">error</span>
          <p style={{ marginTop: "var(--s3)", color: "var(--text-2)" }}>{error}</p>
        </section>
      )}

      {events.length > 0 && (
        <section className="panel">
          <h3 style={{ marginBottom: "var(--s4)" }}>Execution</h3>
          <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--s2)" }}>
            {events.map((event, index) => (
              <li
                key={`${event.node}-${index}`}
                className="rise"
                style={{
                  display: "flex", alignItems: "baseline", gap: "var(--s3)",
                  padding: "var(--s2) 0", borderBottom: "1px solid var(--line)",
                }}
              >
                <span className="mono" style={{ color: "var(--text-3)", minWidth: "2ch" }}>
                  {index + 1}
                </span>
                <span style={{ minWidth: "16ch", fontWeight: 500 }}>
                  {NODE_LABEL[event.node] ?? event.node}
                </span>
                <span className="mono" style={{ color: "var(--text-2)", fontSize: "0.8125rem" }}>
                  {event.node === "retrieve" && `${event.hits} passages${event.degraded ? " · degraded" : ""}`}
                  {event.node === "assess_evidence" && event.rationale}
                  {event.node === "adjudicate" && event.rationale}
                  {event.node === "hypothesise" &&
                    `attempt ${event.attempt}${event.correcting ? ` · correcting ${event.correcting} uncited` : ""}`}
                  {event.node === "verify" &&
                    `${event.citations?.length ?? 0} cited · ${event.uncited?.length ?? 0} uncited`}
                  {event.node === "risk_gate" && event.reason}
                  {["refuse", "escalate", "await_approval", "emit"].includes(event.node) && event.status}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {evidence && (
        <section className="panel">
          <div style={{ display: "flex", gap: "var(--s2)", flexWrap: "wrap", marginBottom: "var(--s4)" }}>
            {verdictChip(evidence.verdict)}
            {riskChip(risk?.risk)}
            {retrieval?.degraded && <span className="chip chip--refused">retrieval degraded</span>}
          </div>
          {retrieval?.top_documents && (
            <p className="mono" style={{ color: "var(--text-3)", fontSize: "0.8125rem" }}>
              searched: {retrieval.top_documents.join(" · ")}
            </p>
          )}
        </section>
      )}

      {outcome === "refuse" && (
        <section className="panel" style={{ borderLeft: "2px solid var(--refused)" }}>
          <span className="chip chip--refused">refused — evidence does not support an answer</span>
          <p style={{ marginTop: "var(--s4)", color: "var(--text-2)" }}>
            {evidence?.rationale}
          </p>
          <p style={{ marginTop: "var(--s3)", color: "var(--text-3)", fontSize: "0.9375rem" }}>
            This is the system working, not failing. Over-refusal costs a follow-up
            question; the other direction costs correctness.
          </p>
        </section>
      )}

      {assessment && outcome !== "refuse" && (
        <section
          className="panel"
          style={{ borderLeft: `2px solid ${rejected ? "var(--blocked)" : "var(--grounded)"}` }}
        >
          <div style={{ display: "flex", gap: "var(--s2)", flexWrap: "wrap", marginBottom: "var(--s4)" }}>
            <h3 style={{ margin: 0 }}>{rejected ? "Draft — not emitted" : "Assessment"}</h3>
          </div>
          {rejected && (
            <div style={{ marginBottom: "var(--s5)" }}>
              <span className="chip chip--blocked">escalated after 3 attempts</span>
              <p style={{ marginTop: "var(--s3)", color: "var(--text-2)" }}>
                {uncited.length} claim{uncited.length === 1 ? "" : "s"} still carried no
                citation, so this was <strong>not emitted</strong>. It is shown because
                hiding it would be worse than labelling it.
              </p>
              {uncited.length > 0 && (
                <ul className="mono" style={{ marginTop: "var(--s3)", color: "var(--blocked)", fontSize: "0.8125rem" }}>
                  {uncited.map((claim, index) => (
                    <li key={index}>{claim.slice(0, 160)}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <pre
            className="mono"
            style={{ whiteSpace: "pre-wrap", margin: 0, color: "var(--text)" }}
          >
            {assessment}
          </pre>

          {citations.length > 0 && (
            <>
              <hr className="hairline" style={{ margin: "var(--s5) 0" }} />
              <h3 style={{ marginBottom: "var(--s3)", fontSize: "1rem" }}>
                Evidence ({citations.length} claims cited)
              </h3>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--s2)" }}>
                {citations.map((citation, index) => (
                  <li key={index}>
                    <button
                      onClick={() =>
                        setOpenCitation(openCitation === `${index}` ? null : `${index}`)
                      }
                      style={{
                        width: "100%", textAlign: "left", background: "var(--surface-2)",
                        borderColor: citation.resolved ? "var(--line)" : "var(--blocked)",
                        padding: "var(--s3)",
                      }}
                    >
                      <span className="mono" style={{ fontSize: "0.8125rem", color: "var(--text-2)" }}>
                        {citation.resolved ? citation.chunk_id : "UNRESOLVED CITATION"}
                      </span>
                      <div style={{ marginTop: "var(--s1)", fontSize: "0.9375rem" }}>
                        {citation.claim}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {proposal && (
        <section
          className="panel"
          style={{
            borderColor:
              risk?.risk === "high" || risk?.risk === "critical" ? "var(--blocked)" : "var(--line)",
          }}
        >
          <h3 style={{ marginBottom: "var(--s3)" }}>Proposed {risk?.risk === "critical" ? "action" : "remediation"}</h3>
          <pre className="mono" style={{ whiteSpace: "pre-wrap", margin: 0 }}>{proposal}</pre>
          {(risk?.risk === "high" || risk?.risk === "critical") && (
            <>
              <hr className="hairline" style={{ margin: "var(--s5) 0" }} />
              <p style={{ color: "var(--text-2)", marginBottom: "var(--s4)" }}>
                This action is above the risk threshold. The run has stopped and nothing
                proceeds until a human decides. Approving starts a new run carrying the
                decision — the approval step cannot auto-proceed.
              </p>
              {/* Neither button is the primary action. A gate where one choice is
                  styled as the obvious one is not a gate. */}
              <div style={{ display: "flex", gap: "var(--s3)" }}>
                <button disabled title="Approval lands in Sprint 6">Approve</button>
                <button disabled title="Approval lands in Sprint 6">Reject</button>
              </div>
            </>
          )}
        </section>
      )}

      {result && (
        <section className="panel">
          <h3 style={{ marginBottom: "var(--s4)" }}>Run</h3>
          <dl
            style={{
              display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
              gap: "var(--s4)", margin: 0,
            }}
          >
            {[
              ["status", result.status],
              ["cost", `$${result.cost_usd.toFixed(6)}`],
              ["claims cited", result.citations],
              ["uncited", result.uncited],
              ["tokens avoided by cache", result.tokens_avoided],
              ["provider events", result.providers.length],
            ].map(([label, value]) => (
              <div key={label as string}>
                <dt style={{ color: "var(--text-3)", fontSize: "0.8125rem" }}>{label}</dt>
                <dd className="mono" style={{ margin: "var(--s1) 0 0", fontSize: "1.125rem" }}>
                  {String(value)}
                </dd>
              </div>
            ))}
          </dl>
          {result.providers.length > 0 && (
            <p className="mono" style={{ color: "var(--text-3)", fontSize: "0.8125rem", marginTop: "var(--s4)" }}>
              {result.providers.map((p) => `${p.provider}:${p.event}`).join("  ")}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
