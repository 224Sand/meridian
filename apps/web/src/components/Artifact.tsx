/**
 * Real system output, rendered as the hero of a scene.
 *
 * The Designer's argument: Apple sells an object and can photograph it. This
 * product's subject is a process, so a data-centre stock shot standing in for
 * it would be decoration in place of substance. Every artifact below is
 * something the system actually produced, quoted rather than illustrated.
 */

export function Frame({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
      <div
        className="mono"
        style={{
          padding: "var(--s3) var(--s4)",
          borderBottom: "1px solid var(--line)",
          color: "var(--text-3)",
          fontSize: "0.75rem",
          letterSpacing: "0.04em",
        }}
      >
        {label}
      </div>
      <div style={{ padding: "var(--s4)" }}>{children}</div>
    </div>
  );
}

export function CitedClaim() {
  return (
    <Frame label="RUN-1A0229ED51D · VERIFY">
      <p className="mono" style={{ fontSize: "0.8125rem", lineHeight: 1.7, margin: 0 }}>
        <span style={{ color: "var(--text)" }}>
          `db.pool.wait_ms` rose before `db.query.p99_ms`, indicating the pool was the cause
        </span>{" "}
        <span style={{ color: "var(--grounded)" }}>[4]</span>
      </p>
      <div
        style={{
          marginTop: "var(--s3)",
          paddingLeft: "var(--s3)",
          borderLeft: "2px solid var(--grounded)",
          color: "var(--text-2)",
          fontSize: "0.8125rem",
        }}
      >
        <span className="mono" style={{ color: "var(--text-3)" }}>
          rb-database-connection-pool#02
        </span>
        <p style={{ margin: "var(--s2) 0 0" }}>
          &ldquo;Compare `db.pool.wait_ms` against `db.query.p99_ms`. If wait time rose
          before query time, the pool is the cause.&rdquo;
        </p>
      </div>
    </Frame>
  );
}

export function Refusal() {
  return (
    <Frame label="RUN · ASSESS_EVIDENCE">
      <span className="chip chip--refused">insufficient</span>
      <p className="mono" style={{ fontSize: "0.8125rem", marginTop: "var(--s3)", color: "var(--text-2)" }}>
        &ldquo;what is the disaster recovery failover procedure&rdquo;
      </p>
      <p style={{ marginTop: "var(--s3)", color: "var(--text-3)", fontSize: "0.8125rem" }}>
        only 20% of the question&rsquo;s terms appear in the retrieved material
      </p>
      <hr className="hairline" style={{ margin: "var(--s4) 0" }} />
      <p className="mono" style={{ fontSize: "0.75rem", color: "var(--text-3)", margin: 0 }}>
        false-answer rate 0.047 [0.029, 0.076] over 319 unanswerable questions
      </p>
    </Frame>
  );
}

export function Waterfall() {
  const spans = [
    { name: "classify", start: 0, ms: 8.7, model: false },
    { name: "retrieve", start: 8.7, ms: 3.8, model: false },
    { name: "assess_evidence", start: 12.5, ms: 0.5, model: false },
    { name: "hypothesise", start: 12.9, ms: 8880, model: true },
    { name: "verify", start: 8893, ms: 1.5, model: false },
    { name: "propose_action", start: 8894, ms: 5100, model: true },
    { name: "risk_gate", start: 13994, ms: 0.4, model: false },
  ];
  const total = 14000;
  return (
    <Frame label="TRACE · 7 SPANS · 14.0S">
      <div style={{ display: "grid", gap: 3 }}>
        {spans.map((span) => (
          <div key={span.name} style={{ display: "grid", gridTemplateColumns: "13ch 1fr", gap: "var(--s2)", alignItems: "center" }}>
            <span className="mono" style={{ fontSize: "0.6875rem", color: "var(--text-3)" }}>
              {span.name}
            </span>
            <div style={{ position: "relative", height: 12, background: "var(--surface-2)", borderRadius: 3 }}>
              <div
                style={{
                  position: "absolute",
                  left: `${(span.start / total) * 100}%`,
                  width: `${Math.max((span.ms / total) * 100, 0.8)}%`,
                  top: 0,
                  bottom: 0,
                  borderRadius: 3,
                  background: span.model ? "var(--accent)" : "var(--grounded)",
                  opacity: span.model ? 0.9 : 0.55,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <p style={{ marginTop: "var(--s3)", color: "var(--text-3)", fontSize: "0.75rem" }}>
        <span style={{ color: "var(--grounded)" }}>■</span> 5 nodes decided by typed rules,
        13.4ms combined · <span style={{ color: "var(--accent)" }}>■</span> 2 model calls, 14.0s
      </p>
    </Frame>
  );
}

export function Failover() {
  return (
    <Frame label="ROUTER · PROVIDER EVENTS">
      <ul className="mono" style={{ listStyle: "none", margin: 0, padding: 0, fontSize: "0.8125rem", display: "grid", gap: "var(--s2)" }}>
        {[
          ["groq", "rate_limit", "consecutive=1", "var(--refused)"],
          ["gemini", "error", "upstream 503", "var(--refused)"],
          ["cerebras", "success", "412ms", "var(--grounded)"],
        ].map(([provider, event, detail, colour]) => (
          <li
            key={provider}
            style={{ display: "grid", gridTemplateColumns: "9ch 11ch 1fr", gap: "var(--s2)" }}
          >
            <span style={{ color: "var(--text)" }}>{provider}</span>
            <span style={{ color: colour }}>{event}</span>
            {/* Wraps rather than clipping. A detail column that overflows its
                frame reads as a broken layout, and the detail is the part that
                explains the event. */}
            <span style={{ color: "var(--text-3)", overflowWrap: "anywhere" }}>{detail}</span>
          </li>
        ))}
      </ul>
      <p style={{ marginTop: "var(--s3)", color: "var(--text-3)", fontSize: "0.75rem" }}>
        A 429 disables a provider for a bounded window. An exhausted quota disables
        it for the process. Conflating them strands the pipeline on its slowest fallback.
      </p>
    </Frame>
  );
}

export function Approval() {
  return (
    <Frame label="RUN · AWAIT_APPROVAL">
      <span className="chip chip--blocked">risk: high — approval required</span>
      <p className="mono" style={{ fontSize: "0.8125rem", marginTop: "var(--s3)", color: "var(--text)" }}>
        Restart the orders-db connection pool on the Tier 0 path.
      </p>
      <hr className="hairline" style={{ margin: "var(--s4) 0" }} />
      <p className="mono" style={{ fontSize: "0.75rem", color: "var(--text-3)", margin: 0, lineHeight: 1.7 }}>
        decision recorded → continuation run-5138840639d1
        <br />
        gated run → <span style={{ color: "var(--blocked)" }}>still awaiting_approval, not resumed</span>
      </p>
    </Frame>
  );
}

export function Budget() {
  return (
    <Frame label="SPEND LEDGER">
      <table className="mono" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.75rem" }}>
        <thead>
          <tr style={{ color: "var(--text-3)", textAlign: "left" }}>
            <th style={{ paddingBottom: "var(--s2)", fontWeight: 450 }}>provider</th>
            <th style={{ paddingBottom: "var(--s2)", fontWeight: 450 }}>reserved</th>
            <th style={{ paddingBottom: "var(--s2)", fontWeight: 450 }}>actual</th>
          </tr>
        </thead>
        <tbody style={{ color: "var(--text-2)" }}>
          {[
            ["mistral", "$0.000603", "$0.000475"],
            ["mistral", "$0.000626", "$0.000407"],
            ["mistral", "$0.000638", "$0.000364"],
          ].map((row, index) => (
            <tr key={index} style={{ borderTop: "1px solid var(--line)" }}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} style={{ padding: "var(--s2) 0" }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ marginTop: "var(--s3)", color: "var(--text-3)", fontSize: "0.75rem" }}>
        Reserved before the call at the price of the most expensive provider that could
        serve it, reconciled after. Ratio 1.50x — a bound, not an estimate.
      </p>
    </Frame>
  );
}
