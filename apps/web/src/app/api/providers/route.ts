/** Live routing order and provider health, proxied from the runtime. */
import { NextResponse } from "next/server";

import { agentServiceToken, agentServiceUrl } from "@/lib/env";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const upstream = await fetch(`${agentServiceUrl()}/v1/providers`, {
      headers: { Authorization: `Bearer ${agentServiceToken()}` },
      cache: "no-store",
    });
    if (!upstream.ok) {
      return NextResponse.json({ error: "runtime_error", status: upstream.status }, { status: 502 });
    }
    return NextResponse.json(await upstream.json());
  } catch (error) {
    return NextResponse.json(
      { error: "runtime_unreachable", detail: error instanceof Error ? error.message : "unknown" },
      { status: 503 },
    );
  }
}
