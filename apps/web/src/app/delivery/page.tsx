import CiStatus from "@/components/CiStatus";
import record from "@/generated/delivery.json";
import config from "@/generated/product.config.json";

export const metadata = { title: `Delivery — ${config.name}` };

/**
 * The delivery record (FR-020 .. FR-024, AC-C12).
 *
 * Every number here is derived by scripts/derive-delivery.mjs from the
 * repository, or read live from the GitHub API. Nothing is typed by hand,
 * because a hand-written test count drifts the moment someone adds a test and
 * forgets, and the entire argument of this page is that its numbers can be
 * checked.
 */

function Stat({ label, value, note }: { label: string; value: string | number; note?: string }) {
  return (
    <div>
      <dt style={{ color: "var(--text-3)", fontSize: "0.8125rem" }}>{label}</dt>
      <dd className="mono" style={{ margin: "var(--s1) 0 0", fontSize: "1.5rem", color: "var(--text)" }}>
        {value}
      </dd>
      {note && (
        <p style={{ color: "var(--text-3)", fontSize: "0.75rem", margin: "var(--s1) 0 0" }}>{note}</p>
      )}
    </div>
  );
}

export default function Delivery() {
  const loc = record.lines;
  const code = loc.agent + loc.tests + loc.web + loc.tooling;

  return (
    <main className="wrap" style={{ paddingTop: "var(--s8)", paddingBottom: "var(--s10)" }}>
      <header style={{ marginBottom: "var(--s7)" }}>
        <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s3)" }}>
          {config.wordmark} / DELIVERY
        </p>
        <h2 style={{ marginBottom: "var(--s4)" }}>The record, not the claim</h2>
        <p style={{ color: "var(--text-2)" }}>
          Every number on this page is derived from the repository at build time or read
          live from the GitHub API. None is typed by hand. The defects are published
          including the ones that were embarrassing, because a delivery record containing
          only successes is not evidence of anything.
        </p>
        <p className="mono" style={{ color: "var(--text-3)", fontSize: "0.75rem", marginTop: "var(--s4)" }}>
          derived at {record.generatedAt} from {record.sha}
        </p>
      </header>

      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <h3 style={{ marginBottom: "var(--s5)" }}>Continuous integration, live</h3>
        <CiStatus />
        <p style={{ color: "var(--text-3)", fontSize: "0.8125rem", marginTop: "var(--s4)" }}>
          Every push runs governance gates, lint, strict type checking, the offline suite,
          integration tests against a real Postgres with pgvector, a statistics suite
          checked against scikit-learn and scipy, a smoke test of the assembled system,
          and both evaluation suites. A red pipeline blocks merge.
        </p>
      </section>

      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <h3 style={{ marginBottom: "var(--s5)" }}>Scale</h3>
        <dl style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--s5)", margin: 0 }}>
          <Stat label="commits" value={record.commits} />
          <Stat
            label="test functions"
            value={record.tests.total}
            note={`across ${record.tests.files} files; pytest reports more because of parametrised expansion`}
          />
          <Stat label="lines of code" value={code.toLocaleString()} note="excluding dependencies and generated files" />
          <Stat label="lines of documentation" value={record.docs.lines.toLocaleString()} note={`${record.docs.files} documents`} />
          <Stat label="code to docs" value={`${(code / record.docs.lines).toFixed(1)}:1`} />
          <Stat label="architecture decisions" value={record.adrs.length} />
        </dl>
      </section>

      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <h3 style={{ marginBottom: "var(--s3)" }}>Defects</h3>
        <p style={{ color: "var(--text-2)", marginBottom: "var(--s5)" }}>
          {record.defects.total} found and fixed during the build, {record.defects.severityOne} of
          them severity one. Every one is guarded by a regression test. <strong>None was found
          by code review.</strong>
        </p>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}>
            <thead>
              <tr style={{ color: "var(--text-3)", textAlign: "left" }}>
                {["id", "sev", "what broke", "root cause"].map((h) => (
                  <th key={h} style={{ padding: "var(--s2) var(--s3) var(--s2) 0", fontWeight: 450 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {record.defects.entries.map((defect) => (
                <tr key={defect.id} style={{ borderTop: "1px solid var(--line)", color: "var(--text-2)" }}>
                  <td className="mono" style={{ padding: "var(--s3) var(--s3) var(--s3) 0", whiteSpace: "nowrap" }}>
                    {defect.id}
                  </td>
                  <td style={{ padding: "var(--s3) var(--s3) var(--s3) 0" }}>
                    <span style={{ color: defect.severity === "1" ? "var(--blocked)" : "var(--text-3)" }}>
                      {defect.severity}
                    </span>
                  </td>
                  <td style={{ padding: "var(--s3) var(--s3) var(--s3) 0", color: "var(--text)" }}>
                    {defect.description}
                  </td>
                  <td style={{ padding: "var(--s3) var(--s3) var(--s3) 0" }}>{defect.cause}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <h3 style={{ marginBottom: "var(--s3)" }}>Requirements</h3>
        <p style={{ color: "var(--text-2)", marginBottom: "var(--s5)" }}>
          {record.requirements.total} requirements, each traced to a story and a named test.
          A requirement with no test fails the build — the gate refuses to pass rather than
          warning, so the traceability matrix cannot quietly go stale.
        </p>
        <dl style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "var(--s5)", margin: 0 }}>
          <Stat label="total" value={record.requirements.total} />
          <Stat label="delivered" value={record.requirements.done} />
          <Stat label="planned" value={record.requirements.planned} />
        </dl>
      </section>

      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <h3 style={{ marginBottom: "var(--s5)" }}>Sprints</h3>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--s2)" }}>
          {record.sprints.map((sprint) => (
            <li
              key={sprint.number}
              style={{ display: "grid", gridTemplateColumns: "4ch 1fr 8ch 1fr", gap: "var(--s3)", padding: "var(--s2) 0", borderBottom: "1px solid var(--line)" }}
            >
              <span className="mono" style={{ color: "var(--text-3)" }}>{sprint.number}</span>
              <span style={{ color: "var(--text)" }}>{sprint.name}</span>
              <span className="mono" style={{ color: "var(--text-3)", fontSize: "0.8125rem" }}>{sprint.release}</span>
              <span className="mono" style={{ color: "var(--text-2)", fontSize: "0.8125rem" }}>{sprint.velocity}</span>
            </li>
          ))}
        </ul>
        <p style={{ color: "var(--text-3)", fontSize: "0.8125rem", marginTop: "var(--s4)" }}>
          Ceremonies map to work sessions rather than calendar days, and that mapping is
          disclosed here rather than dressed up as a two-week cadence. Faking the calendar
          would have made every number on this page fiction.
        </p>
      </section>

      <section className="panel">
        <h3 style={{ marginBottom: "var(--s5)" }}>Architecture decisions</h3>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--s2)" }}>
          {record.adrs.map((adr) => (
            <li
              key={adr.file}
              style={{ display: "grid", gridTemplateColumns: "9ch 1fr", gap: "var(--s3)", padding: "var(--s2) 0", borderBottom: "1px solid var(--line)" }}
            >
              <span className="mono" style={{ color: "var(--text-3)", fontSize: "0.8125rem" }}>
                {adr.status.toLowerCase()}
              </span>
              <a
                href={`https://github.com/${record.repo}/blob/main/docs/03-architecture/adr/${adr.file}`}
                style={{ color: "var(--text-2)", fontSize: "0.9375rem" }}
              >
                {adr.title.replace(/^ADR-\d+\s*—\s*/, "")}
              </a>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
