/**
 * Per-IP rate limiting, failing CLOSED (ADR-0007).
 *
 * The instinctive default is to allow the request when the limiter is
 * unreachable, so an infrastructure blip does not degrade the user experience.
 * Here that default converts a Redis outage into an unbounded-cost incident and
 * turns a public endpoint into free LLM capacity for whoever finds it.
 *
 * The worst outcome of a dependency failure is therefore unavailability, not
 * unbounded spend. For a demonstration that is the correct trade; for a
 * revenue-bearing service it would not be, and the difference is the point.
 */
import "server-only";

import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import { createHash } from "node:crypto";

import { isProduction, perIpLimit, redisConfig } from "./env";

export type Decision = {
  allowed: boolean;
  remaining: number;
  reason: "allowed" | "limit_exceeded" | "limiter_unavailable" | "not_configured";
};

let limiter: Ratelimit | null | undefined;

function get(): Ratelimit | null {
  if (limiter !== undefined) return limiter;
  const config = redisConfig();
  limiter = config
    ? new Ratelimit({
        redis: new Redis(config),
        limiter: Ratelimit.slidingWindow(perIpLimit(), "1 h"),
        prefix: "sandscope:rl",
        analytics: false,
      })
    : null;
  return limiter;
}

/**
 * Hash the address before it goes anywhere.
 *
 * The limiter needs to distinguish visitors, not identify them. A salted digest
 * does the first without the second, and the raw address never leaves the
 * request scope (T-9).
 */
export function identify(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for") ?? "";
  const address = forwarded.split(",")[0]?.trim() || "unknown";
  const salt = process.env.AGENT_SERVICE_TOKEN ?? "sandscope";
  return createHash("sha256").update(`${salt}:${address}`).digest("hex").slice(0, 32);
}

export async function check(request: Request): Promise<Decision> {
  const instance = get();

  if (!instance) {
    // Not configured. Allowed in development so the console runs with no
    // managed services; refused in production, where an unlimited public
    // endpoint is the thing this module exists to prevent.
    return isProduction()
      ? { allowed: false, remaining: 0, reason: "not_configured" }
      : { allowed: true, remaining: perIpLimit(), reason: "not_configured" };
  }

  try {
    const result = await instance.limit(identify(request));
    return {
      allowed: result.success,
      remaining: result.remaining,
      reason: result.success ? "allowed" : "limit_exceeded",
    };
  } catch {
    // FAIL CLOSED. Not a bug, not a fallback, not a TODO.
    return { allowed: false, remaining: 0, reason: "limiter_unavailable" };
  }
}
