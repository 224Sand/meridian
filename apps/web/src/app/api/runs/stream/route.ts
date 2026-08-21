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

/** 16KB. The longest legitimate incident description in the corpus is under
 *  4KB, so this leaves four times the headroom a real submission needs while
 *  still being a bound worth having.
 *
 *  Two earlier numbers were wrong in the same direction. 64KB let the pen
 *  test's own 50KB probe reach a model call. 16KB still admitted bodies the
 *  runtime refuses outright -- it caps `body` at 4000 characters -- so the
 *  edge forwarded requests that could only fail, spending a round trip and a
 *  rate-limit token to learn what it already knew. 8KB holds one runtime-sized
 *  payload plus envelope. test_contract_bff_to_runtime asserts the relation
 *  rather than the constant, so it survives either side moving. */
const MAX_BODY_BYTES = 8 * 1024;

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

  // Body length is a cost bound, not a formality. Everything downstream --
  // retrieval, embedding, the prompt itself -- scales with the text, so an
  // unbounded body is an unbounded bill that the spend guard only catches after
  // the work is under way. Refuse before parsing (P-7).
  //
  // Checked twice on purpose: Content-Length is free but a client controls it,
  // so the parsed text is measured too.
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_BODY_BYTES) {
    return NextResponse.json(
      { error: "payload_too_large", detail: `body exceeds ${MAX_BODY_BYTES} bytes` },
      { status: 413 },
    );
  }

  let raw: string;
  try {
    raw = await request.text();
  } catch {
    return NextResponse.json({ error: "unreadable_body" }, { status: 400 });
  }
  if (new TextEncoder().encode(raw).length > MAX_BODY_BYTES) {
    return NextResponse.json(
      { error: "payload_too_large", detail: `body exceeds ${MAX_BODY_BYTES} bytes` },
      { status: 413 },
    );
  }

  let payload: Body;
  try {
    payload = JSON.parse(raw) as Body;
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
