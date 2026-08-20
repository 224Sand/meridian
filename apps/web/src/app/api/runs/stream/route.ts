/**
 * SSE proxy to the agent runtime.
 *
 * The browser never holds the inter-service token (T-12) and never learns the
 * runtime's URL. This handler is the only thing that does, and it runs on the
 * server exclusively.
 *
 * The stream is piped rather than buffered. Buffering would collect the whole
 * run and deliver it at the end, which is the opposite of the point: a visitor
 * watching an agent reason is watching it happen, not reading a transcript.
 */
import { NextResponse } from "next/server";

import { agentServiceToken, agentServiceUrl } from "@/lib/env";
import { check } from "@/lib/ratelimit";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
/** A run must not outlive the platform's limit silently. */
export const maxDuration = 60;

type Body = {
  workload?: string;
  subject?: string;
  body?: string;
  context?: Record<string, string>;
};

export async function POST(request: Request): Promise<Response> {
  const decision = await check(request);
  if (!decision.allowed) {
    const status = decision.reason === "limiter_unavailable" ? 503 : 429;
    return NextResponse.json(
      {
        error: decision.reason,
        detail:
          decision.reason === "limiter_unavailable"
            ? "the rate limiter is unreachable and this endpoint fails closed"
            : "hourly limit reached for this address",
      },
      { status, headers: { "Retry-After": "3600" } },
    );
  }

  let payload: Body;
  try {
    payload = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "invalid_json" }, { status: 400 });
  }

  if (!payload.workload || !payload.subject || !payload.body) {
    return NextResponse.json(
      { error: "missing_fields", detail: "workload, subject and body are required" },
      { status: 422 },
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${agentServiceUrl()}/v1/runs/stream`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${agentServiceToken()}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        workload: payload.workload,
        subject: payload.subject,
        body: payload.body,
        context: payload.context ?? {},
      }),
    });
  } catch (error) {
    // The runtime sleeps after prolonged inactivity on the free tier (R-01), so
    // an unreachable upstream is an expected state with a specific meaning
    // rather than a generic failure.
    return NextResponse.json(
      {
        error: "runtime_unreachable",
        detail: error instanceof Error ? error.message : "unknown",
      },
      { status: 503 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text().catch(() => "");
    return NextResponse.json(
      { error: "runtime_error", status: upstream.status, detail: text.slice(0, 300) },
      { status: 502 },
    );
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      // Vercel and most proxies buffer by default, which would defeat the
      // stream entirely while everything still appeared to work.
      "X-Accel-Buffering": "no",
      "X-RateLimit-Remaining": String(decision.remaining),
    },
  });
}
