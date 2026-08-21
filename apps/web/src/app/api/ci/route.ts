/**
 * Live CI status from the GitHub API (FR-020).
 *
 * Unauthenticated: the repository is public and the unauthenticated rate limit
 * is 60/hour per IP, which a delivery page comfortably fits inside. Adding a
 * token would mean holding a credential to read public data.
 */
import { NextResponse } from "next/server";

import config from "../../../../../../product.config.json";

export const runtime = "nodejs";
export const revalidate = 300;

type Run = {
  id: number;
  name: string;
  head_branch: string;
  head_sha: string;
  status: string;
  conclusion: string | null;
  created_at: string;
  html_url: string;
  display_title: string;
};

export async function GET(): Promise<Response> {
  try {
    const response = await fetch(
      `https://api.github.com/repos/${config.repo}/actions/runs?per_page=12`,
      {
        headers: { Accept: "application/vnd.github+json", "User-Agent": "sandscope-delivery" },
        next: { revalidate: 300 },
      },
    );
    if (!response.ok) {
      return NextResponse.json(
        { error: "github_error", status: response.status, runs: [] },
        { status: 200 },
      );
    }
    const payload = (await response.json()) as { workflow_runs?: Run[] };
    const runs = (payload.workflow_runs ?? []).map((run) => ({
      id: run.id,
      name: run.name,
      branch: run.head_branch,
      sha: run.head_sha?.slice(0, 7),
      status: run.status,
      conclusion: run.conclusion,
      createdAt: run.created_at,
      url: run.html_url,
      title: run.display_title,
    }));
    return NextResponse.json({ runs });
  } catch (error) {
    // Degrade rather than fail: the rest of the page is derived from the
    // repository and does not depend on GitHub being reachable.
    return NextResponse.json(
      { error: "unreachable", detail: error instanceof Error ? error.message : "unknown", runs: [] },
      { status: 200 },
    );
  }
}
