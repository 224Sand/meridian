/**
 * The request path, drawn as it actually runs.
 *
 * Inline SVG rather than an image so it inherits the theme tokens and stays
 * legible at any zoom. Every box corresponds to a module in the repository; the
 * numbered order is the order a request traverses them, and the two dashed
 * returns are the paths that do NOT reach a provider -- a cache hit and a
 * refusal -- because those are the interesting ones.
 */
export default function SystemMap() {
  const box = { fill: "var(--surface-2)", stroke: "var(--line)", rx: 6 };
  const label = { fill: "var(--text)", fontSize: 11.5, fontFamily: "var(--sans)" } as const;
  const sub = { fill: "var(--text-3)", fontSize: 9.5, fontFamily: "var(--mono)" } as const;

  const Node = ({ x, y, w, t, s }: { x: number; y: number; w: number; t: string; s: string }) => (
    <g>
      <rect x={x} y={y} width={w} height={44} {...box} />
      <text x={x + 12} y={y + 19} {...label}>{t}</text>
      <text x={x + 12} y={y + 34} {...sub}>{s}</text>
    </g>
  );

  return (
    <svg
      viewBox="0 0 880 336"
      role="img"
      aria-label="Request path: browser to edge BFF to agent runtime, through retrieval, the evidence gate, the semantic cache and the provider chain, with dashed returns for cache hits and refusals."
      style={{ width: "100%", height: "auto", display: "block" }}
    >
      <defs>
        <marker id="a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M0 0 L8 4 L0 8 z" fill="var(--text-3)" />
        </marker>
      </defs>

      <text x="0" y="12" {...sub} fill="var(--text-3)">EDGE — vercel dub1</text>
      <Node x={0} y={22} w={190} t="Browser console" s="SSE consumer" />
      <Node x={0} y={86} w={190} t="BFF route handler" s="rate limit · fails closed" />

      <text x={240} y="12" {...sub} fill="var(--text-3)">RUNTIME — hugging face space</text>
      <Node x={240} y={22} w={190} t="Orchestrator" s="langgraph · one chokepoint" />
      <Node x={240} y={86} w={190} t="Hybrid retrieval" s="BM25 + dense" />
      <Node x={240} y={150} w={190} t="Evidence gate" s="3 bands · default refuse" />
      <Node x={240} y={214} w={190} t="Spend guard" s="reserve worst case first" />

      <text x={480} y="12" {...sub} fill="var(--text-3)">PROVIDERS — ordered failover</text>
      <Node x={480} y={22} w={190} t="Semantic cache" s="exact hash, then vector" />
      <Node x={480} y={86} w={190} t="Provider chain" s="5, time-boxed disables" />

      <text x={710} y="12" {...sub} fill="var(--text-3)">DATA — ireland</text>
      <Node x={710} y={86} w={170} t="Neon + pgvector" s="chunks · runs · spans" />
      <Node x={710} y={150} w={170} t="Upstash" s="redis · vector" />

      {[
        [190, 44, 240, 44], [95, 66, 95, 86], [190, 108, 240, 108],
        [335, 66, 335, 86], [335, 130, 335, 150], [335, 194, 335, 214],
        [430, 44, 480, 44], [575, 66, 575, 86], [670, 108, 710, 108],
        [670, 172, 710, 172],
      ].map(([x1, y1, x2, y2], i) => (
        <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--text-3)" strokeWidth="1" markerEnd="url(#a)" />
      ))}

      {/* The two paths that never reach a provider. Each label sits in its own
          lane on the line it describes, masked by a panel-coloured plate so the
          dashes do not run through the words. */}
      <path d="M480 34 L455 34 L455 286 L120 286 L120 130" fill="none" stroke="var(--grounded)"
            strokeWidth="1" strokeDasharray="3 3" markerEnd="url(#a)" />
      <rect x={128} y={278} width={162} height={15} rx={3} fill="var(--surface)" />
      <text x={134} y={289} {...sub} fill="var(--grounded)">cache hit — no provider call</text>

      <path d="M240 172 L215 172 L215 314 L120 314 L120 142" fill="none" stroke="var(--refused)"
            strokeWidth="1" strokeDasharray="3 3" markerEnd="url(#a)" />
      <rect x={128} y={306} width={190} height={15} rx={3} fill="var(--surface)" />
      <text x={134} y={317} {...sub} fill="var(--refused)">INSUFFICIENT — nothing is emitted</text>
    </svg>
  );
}
