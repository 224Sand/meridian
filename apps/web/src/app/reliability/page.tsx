import BudgetBar from "@/components/BudgetBar";
import data from "@/generated/reliability.json";
import config from "../../../../../product.config.json";

export const metadata = { title: `Reliability — ${config.name}` };

/**
 * What the system gets wrong, measured (FR-030..FR-036).
 *
 * Every figure is derived by scripts/derive-surfaces.mjs from the evaluation
 * report, the model metadata training wrote, and the module that enforces the
 * thresholds. The weaknesses section publishes checks that are currently
 * FAILING, on purpose: a page that showed only the passing ones would be the
 * same mistake as the Sprint 2 gate that reported a 0% false-answer rate.
 */

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <dt style={{ color: "var(--text-3)", fontSize: "0.8125rem" }}>{label}</dt>
      <dd className="mono" style={{ margin: "var(--s1) 0 0", fontSize: "1.375rem" }}>{value}</dd>
      {sub && <p style={{ color: "var(--text-3)", fontSize: "0.75rem", margin: "var(--s1) 0 0" }}>{sub}</p>}
    </div>
  );
}

const grid = (min: string) => ({
  display: "grid",
  gap: "var(--s5)",
  gridTemplateColumns: `repeat(auto-fit, minmax(${min}, 1fr))`,
});

export default function Reliability() {
  const { gate, sample, thresholds, model, reranker, defects, weaknesses, postmortems } = data;
  const lift = model.auc - model.baselineAuc;

  return (
    <main className="wrap" style={{ paddingTop: "var(--s8)", paddingBottom: "var(--s10)" }}>
      <header style={{ marginBottom: "var(--s7)" }}>
        <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s3)" }}>
          {config.wordmark} / RELIABILITY
        </p>
        <h2 style={{ marginBottom: "var(--s4)" }}>Measured, including where it fails</h2>
        <p style={{ color: "var(--text-2)" }}>
          An agent that answers everything is not useful; the hard part is knowing when to
          decline. These are the measured error rates of that decision, the thresholds that
          produce them, and the checks that are still failing. The failing ones are published
          because a reliability page listing only successes is the same mistake as the gate
          that once reported a 0% false-answer rate on a sample of 22.
        </p>
      </header>

      <p className="desktop-note">
        Built for a laptop display — everything here works on a phone, but the diagrams
        and tables scroll sideways. Safari or Chrome on a Mac or PC shows it as intended.
      </p>


      {/* ---------------------------------------------------------- the gate */}
      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <h3 style={{ marginBottom: "var(--s3)" }}>The refusal decision</h3>
        <p style={{ color: "var(--text-2)", fontSize: "0.9375rem", marginBottom: "var(--s6)" }}>
          Two thresholds, not chosen by taste. They are read off the ROC curve against
          asymmetric error budgets — answering a question the corpus cannot support is worse
          than declining one it can, so the budgets differ. Measured over{" "}
          <span className="mono">{sample.answerable + sample.unanswerable}</span> labelled
          questions: {sample.answerable} answerable, {sample.unanswerable} unanswerable.
        </p>

        <div style={{ ...grid("280px"), marginBottom: "var(--s6)" }}>
          <BudgetBar
            label="False answers"
            rate={gate.falseAnswer.rate}
            ci={gate.falseAnswer.ci as [number, number]}
            budget={gate.falseAnswer.budget}
            counts={gate.falseAnswer.counts}
          />
          <BudgetBar
            label="False refusals"
            rate={gate.falseRefusal.rate}
            ci={gate.falseRefusal.ci as [number, number]}
            budget={gate.falseRefusal.budget}
            counts={gate.falseRefusal.counts}
          />
        </div>

        <hr className="hairline" style={{ marginBottom: "var(--s5)" }} />

        <dl style={grid("170px")}>
          <Metric
            label="INSUFFICIENT below"
            value={thresholds.insufficientBelow.toFixed(2)}
            sub="refuse — nothing is emitted"
          />
          <Metric
            label="SUFFICIENT above"
            value={thresholds.sufficientAbove.toFixed(2)}
            sub="answer, every claim cited"
          />
          <Metric
            label="Between"
            value="AMBIGUOUS"
            sub="answer, flagged partial — never silently upgraded"
          />
        </dl>
      </section>

      {/* ------------------------------------------------------- the weakness */}
      <section
        className="panel"
        style={{ marginBottom: "var(--s6)", borderColor: "color-mix(in srgb, var(--refused) 30%, var(--line))" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "var(--s4)", marginBottom: "var(--s3)" }}>
          <h3>What is still weak</h3>
          <span className="chip chip--refused">{weaknesses.length} open</span>
        </div>
        <p style={{ color: "var(--text-2)", fontSize: "0.9375rem", marginBottom: "var(--s5)" }}>
          These checks run on every push and are <strong>expected to fail</strong>. They exist
          to keep known limitations visible rather than letting a green suite imply the
          problem was solved. A passing probe suite would mean it had stopped looking.
        </p>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--s4)" }}>
          {weaknesses.map((w) => (
            <li key={w.name} style={{ borderLeft: "2px solid var(--refused)", paddingLeft: "var(--s4)" }}>
              <p className="mono" style={{ fontSize: "0.8125rem", color: "var(--refused)" }}>{w.name}</p>
              <p style={{ color: "var(--text-2)", fontSize: "0.9375rem", marginTop: "var(--s1)" }}>{w.detail}</p>
            </li>
          ))}
        </ul>
      </section>

      {/* ------------------------------------------------------------ models */}
      <div style={{ ...grid("340px"), marginBottom: "var(--s6)" }}>
        <section className="panel">
          <h3 style={{ marginBottom: "var(--s4)" }}>Sufficiency classifier</h3>
          <p style={{ color: "var(--text-2)", fontSize: "0.9375rem", marginBottom: "var(--s5)" }}>
            Gradient boosting over {model.features} retrieval features, trained offline and
            shipped as {model.format.toUpperCase()}. It ships <em>uncalibrated</em>: Platt
            scaling collapsed cross-validated AUC from {model.auc.toFixed(3)} to 0.599, and
            isotonic broke ONNX parity because a step function does not survive float32.
          </p>
          <dl style={grid("120px")}>
            <Metric label="Cross-validated AUC" value={model.auc.toFixed(3)} sub={`baseline ${model.baselineAuc.toFixed(3)} · +${lift.toFixed(3)}`} />
            <Metric label="Training examples" value={String(model.trainedOn)} />
            <Metric label="Recall at operating point" value={model.operatingPoint.recall.toFixed(3)} sub={`FPR ${model.operatingPoint.false_positive_rate.toFixed(3)}`} />
          </dl>
        </section>

        <section className="panel">
          <h3 style={{ marginBottom: "var(--s4)" }}>Cross-encoder re-ranker</h3>
          <p style={{ color: "var(--text-2)", fontSize: "0.9375rem", marginBottom: "var(--s5)" }}>
            {reranker.baseModel} fine-tuned on {reranker.trainingPairs} pairs. Both metrics
            ship: document-level was already {reranker.documentLevelMrr.toFixed(3)} and hid
            the entire effect — measuring at the level a citation actually points at is what
            made the improvement visible.
          </p>
          <dl style={grid("120px")}>
            <Metric label="Chunk MRR, hybrid" value={reranker.chunkLevel.hybrid.toFixed(3)} sub="before re-ranking" />
            <Metric label="Chunk MRR, fine-tuned" value={reranker.chunkLevel.finetuned.toFixed(3)} sub={`pretrained ${reranker.chunkLevel.pretrained.toFixed(3)}`} />
            <Metric label="Re-rank latency p50" value={`${reranker.latencyP50Ms} ms`} sub={`top ${reranker.candidates} candidates`} />
          </dl>
        </section>
      </div>

      {/* ----------------------------------------------------------- defects */}
      <section className="panel" style={{ marginBottom: "var(--s6)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "var(--s4)", marginBottom: "var(--s3)" }}>
          <h3>Defects</h3>
          <span className="chip chip--neutral">
            {defects.total} logged · {defects.severity1} severity 1
          </span>
        </div>
        <p style={{ color: "var(--text-2)", fontSize: "0.9375rem", marginBottom: "var(--s5)" }}>
          Not one was caught by code review, and not one by a unit test written before it.
          Every single one was caught by executing something — the assembled system, a
          measurement over a large labelled set, or a container in CI. That distribution is
          the finding, more than any individual defect.
        </p>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem", minWidth: 640 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--text-3)" }}>
                <th style={{ padding: "var(--s2) var(--s3) var(--s2) 0", fontWeight: 500 }}>ID</th>
                <th style={{ padding: "var(--s2) var(--s3)", fontWeight: 500 }}>Sev</th>
                <th style={{ padding: "var(--s2) var(--s3)", fontWeight: 500 }}>Defect</th>
              </tr>
            </thead>
            <tbody>
              {defects.rows.map((d) => (
                <tr key={d.id} style={{ borderTop: "1px solid var(--line)", verticalAlign: "top" }}>
                  <td className="mono" style={{ padding: "var(--s3) var(--s3) var(--s3) 0", color: "var(--text-2)", whiteSpace: "nowrap" }}>{d.id}</td>
                  <td className="mono" style={{ padding: "var(--s3)", color: d.severity === "1" ? "var(--blocked)" : "var(--text-3)" }}>{d.severity}</td>
                  <td style={{ padding: "var(--s3)", color: "var(--text-2)" }}>{d.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ------------------------------------------------------ postmortems */}
      <section className="panel">
        <h3 style={{ marginBottom: "var(--s4)" }}>Postmortems</h3>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--s4)" }}>
          {postmortems.map((p) => (
            <li key={p.file}>
              <a
                href={`https://github.com/${config.repo}/blob/main/docs/06-operations/postmortems/${p.file}`}
                style={{ color: "var(--text)" }}
              >
                {p.title}
              </a>
              <p className="mono" style={{ color: "var(--text-3)", fontSize: "0.75rem", marginTop: "var(--s1)" }}>{p.date}</p>
            </li>
          ))}
        </ul>
      </section>

      <p className="mono" style={{ color: "var(--text-3)", fontSize: "0.75rem", marginTop: "var(--s6)" }}>
        derived at {data.generatedAt} from {data.sha}
      </p>
    </main>
  );
}
