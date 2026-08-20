/** Shapes of the SSE events the runtime emits. Kept in one place so the console
 *  and any future consumer disagree loudly rather than quietly. */

export type NodeName =
  | "classify" | "retrieve" | "assess_evidence" | "adjudicate"
  | "hypothesise" | "verify" | "propose_action" | "risk_gate"
  | "refuse" | "escalate" | "await_approval" | "emit";

export type Citation = {
  claim: string;
  chunk_id: string | null;
  resolved: boolean;
};

export type Span = {
  name: NodeName;
  start_ms: number;
  duration_ms: number;
  calls: number;
  cache_hits: number;
};

export type LedgerEntry = {
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  estimated_usd: number;
  actual_usd: number;
  cache_hit: boolean;
};

export type NodeEvent = {
  node: NodeName;
  duration_ms?: number;
  hits?: number;
  degraded?: boolean;
  top_documents?: string[];
  verdict?: "sufficient" | "insufficient" | "ambiguous";
  rationale?: string;
  attempt?: number;
  correcting?: number;
  text?: string;
  citations?: Citation[];
  uncited?: string[];
  proposal?: string;
  risk?: "low" | "medium" | "high" | "critical";
  reason?: string;
  status?: string;
};

export type RunCompleted = {
  run_id: string;
  status: "completed" | "refused" | "escalated" | "awaiting_approval" | "failed";
  risk: string | null;
  citations: number;
  uncited: number;
  cost_usd: number;
  tokens_avoided: number;
  providers: { provider: string; event: string }[];
  total_ms: number;
  spans: Span[];
  ledger: LedgerEntry[];
};

export type StreamEvent =
  | { kind: "run_started"; data: { run_id: string; workload: string } }
  | { kind: "node_completed"; data: NodeEvent }
  | { kind: "run_completed"; data: RunCompleted }
  | { kind: "error"; data: { error: string; detail: string } };

/**
 * Parse an SSE byte stream into typed events.
 *
 * Written by hand rather than using EventSource because EventSource cannot
 * issue a POST, and the run parameters belong in a body rather than a query
 * string.
 */
export async function* readEvents(response: Response): AsyncGenerator<StreamEvent> {
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Events are separated by a blank line. A partial event stays in the buffer
    // until its terminator arrives; splitting on newline alone would emit half
    // a JSON payload the moment a chunk boundary landed mid-event.
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      let kind = "";
      let payload = "";
      for (const line of part.split("\n")) {
        if (line.startsWith("event: ")) kind = line.slice(7).trim();
        else if (line.startsWith("data: ")) payload += line.slice(6);
      }
      if (!kind || !payload) continue;
      try {
        yield { kind, data: JSON.parse(payload) } as StreamEvent;
      } catch {
        // A malformed frame is dropped rather than aborting the stream: one bad
        // event should not end a run the user is watching.
      }
    }
  }
}
