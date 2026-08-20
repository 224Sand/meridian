"use client";

/**
 * Execution trace as a waterfall.
 *
 * Row width is duration, so the question "why did that take so long" is
 * answered by looking rather than by reading numbers. Provider hops and cache
 * outcomes are annotations ON the row rather than a separate view: the answer
 * lives in one place or it is not an answer.
 */

import type { LedgerEntry, Span } from "@/lib/events";

const LABEL: Record<string, string> = {
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

/** Nodes that make no model call are the product's cost story, so they are
 *  coloured as such rather than left to look like everything else. */
const DETERMINISTIC = new Set(["classify", "retrieve", "assess_evidence", "verify", "risk_gate"]);

export default function Trace({
  spans,
  ledger,
  totalMs,
}: {
  spans: Span[];
  ledger: LedgerEntry[];
  totalMs: number;
}) {
  if (spans.length === 0) return null;
  const scale = Math.max(totalMs, 1);

  return (
    <section className="panel">
      <h3 style={{ marginBottom: "var(--s2)" }}>Trace</h3>
      <p style={{ color: "var(--text-3)", fontSize: "0.8125rem", marginBottom: "var(--s5)" }}>
        {spans.length} spans · {totalMs.toFixed(0)}ms total ·{" "}
        {spans.filter((s) => DETERMINISTIC.has(s.name)).length} nodes decided without a model call
      </p>

      <div style={{ display: "grid", gap: "var(--s1)" }}>
        {spans.map((span, index) => {
          const left = (span.start_ms / scale) * 100;
          const width = Math.max((span.duration_ms / scale) * 100, 0.6);
          const deterministic = DETERMINISTIC.has(span.name);
          return (
            <div
              key={`${span.name}-${index}`}
              style={{ display: "grid", gridTemplateColumns: "15ch 1fr 9ch", gap: "var(--s3)", alignItems: "center" }}
            >
              <span style={{ fontSize: "0.8125rem", color: "var(--text-2)" }}>
                {LABEL[span.name] ?? span.name}
              </span>
              <div style={{ position: "relative", height: 20, background: "var(--surface-2)", borderRadius: 4 }}>
                <div
                  title={`${span.duration_ms.toFixed(1)}ms${span.calls ? ` · ${span.calls} model call(s)` : " · no model call"}`}
                  style={{
                    position: "absolute",
                    left: `${left}%`,
                    width: `${width}%`,
                    top: 0,
                    bottom: 0,
                    borderRadius: 4,
                    background: deterministic ? "var(--grounded)" : "var(--accent)",
                    opacity: deterministic ? 0.55 : 0.9,
                  }}
                />
                {span.cache_hits > 0 && (
                  <span
                    className="mono"
                    style={{
                      position: "absolute",
                      left: `calc(${left}% + 6px)`,
                      fontSize: "0.6875rem",
                      lineHeight: "20px",
                      color: "#001",
                    }}
                  >
                    cache
                  </span>
                )}
              </div>
              <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-3)", textAlign: "right" }}>
                {span.duration_ms.toFixed(0)}ms
              </span>
            </div>
          );
        })}
      </div>

      <p style={{ color: "var(--text-3)", fontSize: "0.75rem", marginTop: "var(--s4)" }}>
        <span style={{ color: "var(--grounded)" }}>■</span> decided by a typed rule, no tokens spent
        {"   "}
        <span style={{ color: "var(--accent)" }}>■</span> model call
      </p>

      {ledger.length > 0 && (
        <>
          <hr className="hairline" style={{ margin: "var(--s5) 0" }} />
          <h3 style={{ fontSize: "1rem", marginBottom: "var(--s3)" }}>Spend ledger</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="mono" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}>
              <thead>
                <tr style={{ color: "var(--text-3)", textAlign: "left" }}>
                  {["provider", "model", "in", "out", "estimated", "actual"].map((h) => (
                    <th key={h} style={{ padding: "var(--s2) var(--s3) var(--s2) 0", fontWeight: 450 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ledger.map((entry, index) => (
                  <tr key={index} style={{ borderTop: "1px solid var(--line)", color: "var(--text-2)" }}>
                    <td style={{ padding: "var(--s2) var(--s3) var(--s2) 0" }}>
                      {entry.cache_hit ? <span style={{ color: "var(--grounded)" }}>cache</span> : entry.provider}
                    </td>
                    <td style={{ padding: "var(--s2) var(--s3) var(--s2) 0" }}>{entry.model}</td>
                    <td style={{ padding: "var(--s2) var(--s3) var(--s2) 0" }}>{entry.tokens_in}</td>
                    <td style={{ padding: "var(--s2) var(--s3) var(--s2) 0" }}>{entry.tokens_out}</td>
                    <td style={{ padding: "var(--s2) var(--s3) var(--s2) 0" }}>
                      ${entry.estimated_usd.toFixed(6)}
                    </td>
                    <td style={{ padding: "var(--s2) var(--s3) var(--s2) 0", color: "var(--text)" }}>
                      ${entry.actual_usd.toFixed(6)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ color: "var(--text-3)", fontSize: "0.75rem", marginTop: "var(--s3)" }}>
            The estimate is taken before each call fires and the actual is written after.
            Pricing after the fact is accounting; pricing before is control.
          </p>
        </>
      )}
    </section>
  );
}
