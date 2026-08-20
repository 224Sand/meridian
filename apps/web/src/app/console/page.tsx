import Console from "@/components/Console";
import config from "../../../../../product.config.json";

export const metadata = { title: `Console — ${config.name}` };

export default function ConsolePage() {
  return (
    <main className="wrap" style={{ paddingTop: "var(--s8)", paddingBottom: "var(--s10)" }}>
      <header style={{ marginBottom: "var(--s7)" }}>
        <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s3)" }}>
          {config.wordmark} / CONSOLE
        </p>
        <h2 style={{ marginBottom: "var(--s4)" }}>Watch it reason</h2>
        <p style={{ color: "var(--text-2)" }}>
          Every claim is cited to a passage. Where the evidence does not support an
          answer, it says so. Anything above the risk threshold stops for a human.
          The numbers below are from the run you just watched.
        </p>
      </header>
      <Console />
    </main>
  );
}
