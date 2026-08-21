import SystemMap from "@/components/SystemMap";
import data from "@/generated/architecture.json";
import config from "../../../../../product.config.json";

export const metadata = { title: `Architecture — ${config.name}` };

/**
 * The decisions, not the diagram (FR-040..FR-046).
 *
 * The ADR list, their statuses and the provider order are parsed from the
 * repository by scripts/derive-surfaces.mjs -- the chain in particular is read
 * out of the function that builds it, so reordering the code reorders this page
 * rather than leaving it quietly wrong.
 */
export default function Architecture() {
  const { adrs, providers, counts } = data;

  return (
    <main className="wrap" style={{ paddingTop: "var(--s8)", paddingBottom: "var(--s10)" }}>
      <header style={{ marginBottom: "var(--s7)" }}>
        <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s3)" }}>
          {config.wordmark} / ARCHITECTURE
        </p>
        <h2 style={{ marginBottom: "var(--s4)" }}>Decisions, and what they cost</h2>
        <p style={{ color: "var(--text-2)" }}>
          {counts.adrs} architecture decision records, {counts.accepted} accepted. Each one
          names the alternative it rejected and what the choice gives up, because a decision
          record that lists only advantages is marketing. Two of these were written after
          being measured wrong the first time.
        </p>
      </header>

      <p className="desktop-note">
        Built for a laptop display — everything here works on a phone, but the diagrams
        and tables scroll sideways. Safari or Chrome on a Mac or PC shows it as intended.
      </p>


      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <h3 style={{ marginBottom: "var(--s5)" }}>Request path</h3>
        {/* Scrolls inside its own box below ~700px rather than scaling its
            labels down to an unreadable size. See globals.css. */}
        <div className="scroll-x">
          <div style={{ minWidth: 720 }}>
            <SystemMap />
          </div>
        </div>
        <p style={{ color: "var(--text-3)", fontSize: "0.8125rem", marginTop: "var(--s5)" }}>
          The two dashed returns are the paths that never reach a model: a semantic cache hit,
          and an <span className="mono">INSUFFICIENT</span> verdict. The second emits nothing
          at all — no draft is rendered, which is enforced in the console rather than assumed,
          after it once displayed output the governance layer had refused (D-009).
        </p>
      </section>

      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <h3 style={{ marginBottom: "var(--s3)" }}>Provider order</h3>
        <p style={{ color: "var(--text-2)", fontSize: "0.9375rem", marginBottom: "var(--s5)" }}>
          Fixed, not adaptive. A provider that rate-limits is disabled for a bounded interval
          rather than the process lifetime, and the clock is injected so expiry is tested
          instead of waited on. Spend is reserved against the worst-case <em>surviving</em>{" "}
          provider before the call — pricing the first one under-reserved by 4× the moment
          failover reached a costlier model (D-010).
        </p>
        <ol
          style={{
            listStyle: "none", margin: 0, padding: 0,
            display: "flex", flexWrap: "wrap", gap: "var(--s3)", alignItems: "center",
          }}
        >
          {providers.map((p, i) => (
            <li key={p} style={{ display: "flex", alignItems: "center", gap: "var(--s3)" }}>
              <span className="chip chip--neutral">
                <span className="mono" style={{ color: "var(--text-3)" }}>{i + 1}</span>
                &nbsp;{p}
              </span>
              {i < providers.length - 1 && <span style={{ color: "var(--text-3)" }}>→</span>}
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h3 style={{ marginBottom: "var(--s5)" }}>Decision records</h3>
        <ol style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--s4)" }}>
          {adrs.map((a) => (
            <li key={a.id} className="panel">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "var(--s4)", flexWrap: "wrap" }}>
                <a
                  href={`https://github.com/${config.repo}/blob/main/docs/03-architecture/adr/`}
                  style={{ color: "var(--text)", fontSize: "1.0625rem", fontWeight: 590, letterSpacing: "-0.01em" }}
                >
                  <span className="mono" style={{ color: "var(--text-3)", fontSize: "0.8125rem" }}>ADR-{a.id}</span>
                  {"  "}{a.title}
                </a>
                <span className={`chip ${a.status === "Accepted" ? "chip--grounded" : "chip--neutral"}`}>{a.status}</span>
              </div>
              {a.context && (
                <p style={{ color: "var(--text-2)", fontSize: "0.9375rem", marginTop: "var(--s3)" }}>{a.context}</p>
              )}
            </li>
          ))}
        </ol>
      </section>

      <p className="mono" style={{ color: "var(--text-3)", fontSize: "0.75rem", marginTop: "var(--s6)" }}>
        derived at {data.generatedAt} from {data.sha}
      </p>
    </main>
  );
}
