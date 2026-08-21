/**
 * A measured error rate against the budget that defines it.
 *
 * Draws the point estimate, its 95% confidence interval, and the budget line on
 * one axis, because the interesting question is never "what is the rate" but
 * "is the interval clear of the line". A bare number hides the case where the
 * estimate passes and the interval straddles the budget -- which is exactly the
 * mistake that produced D-001, where a rate measured on too small a sample was
 * reported as certain.
 *
 * Colour never carries the verdict alone: the state is written out in text.
 */
export default function BudgetBar({
  label,
  rate,
  ci,
  budget,
  counts,
}: {
  label: string;
  rate: number;
  ci: [number, number];
  budget: number;
  counts: string | null;
}) {
  // Scale so the budget sits at 60% of the width regardless of magnitude,
  // keeping the two panels visually comparable even though the budgets differ.
  const max = Math.max(budget / 0.6, ci[1] * 1.15);
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;

  // Three states, not two. The point estimate passing and the interval being
  // clear of the budget are different claims, and collapsing them is how a
  // result gets over-reported -- the exact failure behind D-001, where a rate
  // measured on a small sample was presented as settled.
  const over = rate >= budget;
  const clear = ci[1] < budget;
  const state = over
    ? "over budget"
    : clear
      ? "clear of budget"
      : "within budget, interval not yet tight";
  const tone = over ? "blocked" : clear ? "grounded" : "refused";

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: "var(--s4)" }}>
        <h3 style={{ fontSize: "1rem" }}>{label}</h3>
        <span className={`chip chip--${tone}`}>{state}</span>
      </div>

      <div
        style={{
          position: "relative",
          height: 46,
          marginTop: "var(--s4)",
          background: "var(--surface-2)",
          borderRadius: 6,
          border: "1px solid var(--line)",
          overflow: "hidden",
        }}
      >
        {/* confidence interval */}
        <div
          style={{
            position: "absolute", top: "50%", transform: "translateY(-50%)",
            left: pct(ci[0]), width: `calc(${pct(ci[1])} - ${pct(ci[0])})`,
            height: 10, borderRadius: 5,
            background: `color-mix(in srgb, var(--${tone}) 30%, transparent)`,
          }}
        />
        {/* point estimate */}
        <div
          style={{
            position: "absolute", top: "50%", transform: "translate(-50%, -50%)",
            left: pct(rate), width: 3, height: 22, borderRadius: 2,
            background: `var(--${tone})`,
          }}
        />
        {/* budget line */}
        <div
          style={{
            position: "absolute", top: 0, bottom: 0, left: pct(budget),
            width: 1, background: "var(--text-3)",
          }}
        />
        <span
          className="mono"
          style={{
            position: "absolute", top: 4, left: `calc(${pct(budget)} + 6px)`,
            fontSize: "0.6875rem", color: "var(--text-3)",
          }}
        >
          budget {(budget * 100).toFixed(0)}%
        </span>
      </div>

      <p className="mono" style={{ fontSize: "0.8125rem", color: "var(--text-2)", marginTop: "var(--s3)" }}>
        {(rate * 100).toFixed(1)}%{" "}
        <span style={{ color: "var(--text-3)" }}>
          95% CI [{(ci[0] * 100).toFixed(1)}, {(ci[1] * 100).toFixed(1)}]
          {counts ? ` · ${counts}` : ""}
        </span>
      </p>
    </div>
  );
}
