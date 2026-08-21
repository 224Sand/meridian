/** Record an approval decision. The gated run is never resumed (ADR-0006). */
import { NextResponse } from "next/server";

import { agentServiceToken, agentServiceUrl } from "@/lib/env";
import { check } from "@/lib/ratelimit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  context: { params: Promise<unknown> },
): Promise<Response> {
  const decision = await check(request);
  if (!decision.allowed) {
    return NextResponse.json({ error: decision.reason }, { status: 429 });
  }

  // Typed loosely at the boundary and narrowed here. Next's generated route
  // validator requires the context param to be Promise<unknown>, and a dynamic
  // segment is untrusted input regardless of what the framework types say.
  const resolved = (await context.params) as { runId?: unknown };
  const runId = typeof resolved.runId === "string" ? resolved.runId : "";
  if (!runId) {
    return NextResponse.json({ error: "missing_run_id" }, { status: 400 });
  }
  let body: { decision?: string };
  try {
    body = (await request.json()) as { decision?: string };
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }
  if (body.decision !== "approved" && body.decision !== "rejected") {
    return NextResponse.json(
      { error: "invalid_decision", detail: "decision must be approved or rejected" },
      { status: 422 },
    );
  }

  try {
    const upstream = await fetch(
      `${agentServiceUrl()}/v1/runs/${encodeURIComponent(runId)}/approve`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${agentServiceToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ decision: body.decision, decided_by: "console" }),
      },
    );
    const payload = await upstream.json().catch(() => ({}));
    return NextResponse.json(payload, { status: upstream.status });
  } catch (error) {
    return NextResponse.json(
      { error: "runtime_unreachable", detail: error instanceof Error ? error.message : "unknown" },
      { status: 503 },
    );
  }
}
