"use client";

import { useEffect, useState } from "react";

type Run = {
  id: number; name: string; branch: string; sha: string;
  status: string; conclusion: string | null; createdAt: string; url: string; title: string;
};

export default function CiStatus() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/api/ci")
      .then((r) => r.json())
      .then((d) => {
        setRuns(d.runs ?? []);
        setFailed(Boolean(d.error));
      })
      .catch(() => setFailed(true));
  }, []);

  if (runs === null) {
    return <p className="mono" style={{ color: "var(--text-3)" }}>reading GitHub…</p>;
  }
  if (failed && runs.length === 0) {
    return (
      <p className="mono" style={{ color: "var(--text-3)" }}>
        GitHub is unreachable. Everything else on this page is derived from the
        repository and does not depend on it.
      </p>
    );
  }

  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "var(--s2)" }}>
      {runs.map((run) => {
        const ok = run.conclusion === "success";
        const running = run.status !== "completed";
        return (
          <li key={run.id}>
            <a
              href={run.url}
              style={{
                display: "grid", gridTemplateColumns: "10ch 8ch 1fr auto", gap: "var(--s3)",
                alignItems: "center", padding: "var(--s2) 0",
                borderBottom: "1px solid var(--line)", color: "inherit", textDecoration: "none",
              }}
            >
              <span
                className="chip"
                style={{
                  color: running ? "var(--text-2)" : ok ? "var(--grounded)" : "var(--blocked)",
                  borderColor: "var(--line)",
                }}
              >
                {running ? "running" : ok ? "pass" : "fail"}
              </span>
              <span className="mono" style={{ color: "var(--text-3)", fontSize: "0.75rem" }}>
                {run.sha}
              </span>
              <span style={{ fontSize: "0.875rem", color: "var(--text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {run.title}
              </span>
              <span className="mono" style={{ color: "var(--text-3)", fontSize: "0.75rem" }}>
                {run.name}
              </span>
            </a>
          </li>
        );
      })}
    </ul>
  );
}
