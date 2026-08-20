/**
 * Server-only environment access.
 *
 * Every value here is read in route handlers and never in a component. The
 * inter-service token in particular must never reach the browser (T-12), and
 * the reliable way to guarantee that is for the module that reads it to be
 * unimportable from client code.
 */
import "server-only";

function required(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    // Fail loudly at the first request rather than sending an unauthenticated
    // call to the runtime and reporting its 401 as if the user did something
    // wrong.
    throw new Error(`${name} is not set; the BFF cannot reach the agent runtime`);
  }
  return value;
}

export const agentServiceUrl = (): string =>
  (process.env.AGENT_SERVICE_URL?.trim() || "http://localhost:7860").replace(/\/$/, "");

export const agentServiceToken = (): string => required("AGENT_SERVICE_TOKEN");

/** Rate limiting is optional in development and required in production. */
export const redisConfig = (): { url: string; token: string } | null => {
  const url = process.env.UPSTASH_REDIS_REST_URL?.trim();
  const token = process.env.UPSTASH_REDIS_REST_TOKEN?.trim();
  return url && token ? { url, token } : null;
};

export const perIpLimit = (): number =>
  Number.parseInt(process.env.PER_IP_RATE_LIMIT_PER_HOUR ?? "20", 10) || 20;

export const isProduction = (): boolean => process.env.NODE_ENV === "production";
