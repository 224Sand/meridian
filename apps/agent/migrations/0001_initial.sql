-- 0001_initial — MERIDIAN control plane schema
--
-- Forward-only. Migrations are never edited after they have been applied
-- anywhere; a correction is a new migration.
--
-- Design notes that are load-bearing rather than stylistic:
--   * chunk_embedding is keyed (chunk_id, model). Two embedding models produce
--     vectors in incomparable spaces, so they must never share a column
--     (ADR-0005). The unique constraint makes the mistake impossible to make.
--   * session stores a salted hash of the client address, never the address
--     (THREAT_MODEL T-9).
--   * spend_ledger.estimated_cost_usd is NOT NULL because the estimate is taken
--     BEFORE the call. Pricing after the fact is accounting, not control
--     (ADR-0007).
--   * approval has a unique constraint on run_id: a run has at most one
--     approval, and the continuation is a separate run (ADR-0006).

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─── Simulated production estate ────────────────────────────────────────────

CREATE TABLE service (
    id            TEXT PRIMARY KEY,
    name          TEXT        NOT NULL UNIQUE,
    tier          SMALLINT    NOT NULL CHECK (tier BETWEEN 0 AND 3),
    owner_team    TEXT        NOT NULL,
    runtime       TEXT        NOT NULL,
    region        TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON COLUMN service.tier IS '0 = customer-facing critical, 3 = internal batch';

CREATE TABLE service_dependency (
    upstream_id   TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    downstream_id TEXT NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    kind          TEXT NOT NULL CHECK (kind IN ('sync', 'async', 'datastore')),
    PRIMARY KEY (upstream_id, downstream_id),
    CHECK (upstream_id <> downstream_id)
);

CREATE TABLE telemetry_event (
    id          BIGSERIAL PRIMARY KEY,
    service_id  TEXT        NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    observed_at TIMESTAMPTZ NOT NULL,
    kind        TEXT        NOT NULL CHECK (kind IN ('metric', 'log', 'trace')),
    name        TEXT        NOT NULL,
    value       DOUBLE PRECISION,
    payload     JSONB       NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX telemetry_event_service_time_idx ON telemetry_event (service_id, observed_at DESC);

CREATE TABLE incident (
    id           TEXT PRIMARY KEY,
    service_id   TEXT        NOT NULL REFERENCES service(id) ON DELETE CASCADE,
    title        TEXT        NOT NULL,
    signature    TEXT        NOT NULL,
    severity     SMALLINT    NOT NULL CHECK (severity BETWEEN 1 AND 4),
    status       TEXT        NOT NULL DEFAULT 'open'
                             CHECK (status IN ('open', 'triaging', 'mitigated', 'resolved')),
    opened_at    TIMESTAMPTZ NOT NULL,
    resolved_at  TIMESTAMPTZ,
    seed         BIGINT      NOT NULL,
    CHECK (resolved_at IS NULL OR resolved_at >= opened_at)
);
CREATE INDEX incident_status_opened_idx ON incident (status, opened_at DESC);
COMMENT ON COLUMN incident.seed IS 'Reproduces this incident exactly; a failing demo is replayable from this alone.';

-- ─── Retrieval corpus ───────────────────────────────────────────────────────

CREATE TABLE document (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL CHECK (kind IN ('runbook', 'postmortem', 'policy', 'architecture')),
    title      TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunk (
    id          TEXT PRIMARY KEY,
    document_id TEXT     NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    ordinal     INTEGER  NOT NULL,
    heading     TEXT,
    body        TEXT     NOT NULL CHECK (length(body) > 0),
    token_count INTEGER  NOT NULL CHECK (token_count > 0),
    UNIQUE (document_id, ordinal)
);

CREATE TABLE chunk_embedding (
    chunk_id   TEXT        NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,
    model      TEXT        NOT NULL,
    dim        INTEGER     NOT NULL CHECK (dim > 0),
    vec        vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (chunk_id, model)
);
CREATE INDEX chunk_embedding_model_idx ON chunk_embedding (model);
CREATE INDEX chunk_embedding_vec_idx ON chunk_embedding USING hnsw (vec vector_cosine_ops);
COMMENT ON TABLE chunk_embedding IS
  'ADR-0005: vectors from different models are never compared. Every query filters on model.';

-- ─── Sessions and memory ────────────────────────────────────────────────────

CREATE TABLE session (
    id           TEXT PRIMARY KEY,
    ip_hash      TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (length(ip_hash) = 64)
);
COMMENT ON COLUMN session.ip_hash IS 'Salted SHA-256. The raw address is never persisted (T-9).';

CREATE TABLE memory_item (
    id         BIGSERIAL PRIMARY KEY,
    session_id TEXT        NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    kind       TEXT        NOT NULL CHECK (kind IN ('fact', 'preference', 'incident_ref')),
    content    TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memory_item_session_idx ON memory_item (session_id, created_at DESC);

-- ─── Agent execution ────────────────────────────────────────────────────────

CREATE TABLE run (
    id            TEXT PRIMARY KEY,
    incident_id   TEXT        REFERENCES incident(id) ON DELETE SET NULL,
    session_id    TEXT        NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    parent_run_id TEXT        REFERENCES run(id) ON DELETE SET NULL,
    status        TEXT        NOT NULL DEFAULT 'running'
                              CHECK (status IN ('running','completed','refused','escalated',
                                                'awaiting_approval','failed','incomplete')),
    verdict       TEXT,
    confidence    DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    degraded      BOOLEAN     NOT NULL DEFAULT FALSE,
    tokens_in     INTEGER     NOT NULL DEFAULT 0 CHECK (tokens_in >= 0),
    tokens_out    INTEGER     NOT NULL DEFAULT 0 CHECK (tokens_out >= 0),
    cost_usd      NUMERIC(12,6) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at      TIMESTAMPTZ,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX run_session_idx ON run (session_id, started_at DESC);
COMMENT ON COLUMN run.parent_run_id IS
  'A continuation after human approval is a NEW run pointing back at the gated one (ADR-0006).';
COMMENT ON COLUMN run.degraded IS
  'True when retrieval ran lexical-only because the embedding provider was unavailable (ADR-0004).';

CREATE TABLE span (
    id             TEXT PRIMARY KEY,
    run_id         TEXT        NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    parent_span_id TEXT        REFERENCES span(id) ON DELETE CASCADE,
    trace_id       TEXT        NOT NULL,
    name           TEXT        NOT NULL,
    kind           TEXT        NOT NULL CHECK (kind IN ('internal','client','server','producer','consumer')),
    status         TEXT        NOT NULL DEFAULT 'unset' CHECK (status IN ('unset','ok','error')),
    started_at     TIMESTAMPTZ NOT NULL,
    ended_at       TIMESTAMPTZ,
    attributes     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);
CREATE INDEX span_run_idx   ON span (run_id, started_at);
CREATE INDEX span_trace_idx ON span (trace_id);

CREATE TABLE citation (
    id         BIGSERIAL PRIMARY KEY,
    run_id     TEXT             NOT NULL REFERENCES run(id) ON DELETE CASCADE,
    claim_text TEXT             NOT NULL CHECK (length(claim_text) > 0),
    chunk_id   TEXT             NOT NULL REFERENCES chunk(id) ON DELETE RESTRICT,
    score      DOUBLE PRECISION NOT NULL,
    ordinal    INTEGER          NOT NULL
);
CREATE INDEX citation_run_idx ON citation (run_id, ordinal);

CREATE TABLE approval (
    id           BIGSERIAL PRIMARY KEY,
    run_id       TEXT        NOT NULL UNIQUE REFERENCES run(id) ON DELETE CASCADE,
    action       TEXT        NOT NULL,
    risk_level   TEXT        NOT NULL CHECK (risk_level IN ('low','medium','high','critical')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decision     TEXT        CHECK (decision IN ('approved','rejected')),
    decided_at   TIMESTAMPTZ,
    decided_by   TEXT,
    CHECK ((decision IS NULL) = (decided_at IS NULL)),
    CHECK ((decision IS NULL) = (decided_by IS NULL))
);
COMMENT ON TABLE approval IS
  'One approval per run. The continuation is a separate run, so this cannot auto-proceed (ADR-0006).';

-- ─── Control plane telemetry ────────────────────────────────────────────────

CREATE TABLE cache_entry (
    id              BIGSERIAL PRIMARY KEY,
    prompt_hash     TEXT        NOT NULL,
    embedding_model TEXT        NOT NULL,
    model_tier      TEXT        NOT NULL CHECK (model_tier IN ('fast','large')),
    prompt_vec      vector(768),
    response        TEXT        NOT NULL,
    tokens_in       INTEGER     NOT NULL CHECK (tokens_in >= 0),
    tokens_out      INTEGER     NOT NULL CHECK (tokens_out >= 0),
    hits            INTEGER     NOT NULL DEFAULT 0 CHECK (hits >= 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (prompt_hash, embedding_model, model_tier)
);
CREATE INDEX cache_entry_vec_idx ON cache_entry USING hnsw (prompt_vec vector_cosine_ops);
COMMENT ON TABLE cache_entry IS
  'embedding_model is part of the key: a lookup under a different model is a MISS, never a cross-space comparison (ADR-0005).';

CREATE TABLE provider_event (
    id         BIGSERIAL PRIMARY KEY,
    provider   TEXT        NOT NULL,
    event      TEXT        NOT NULL CHECK (event IN ('success','rate_limit','error','disabled','reenabled','injected_failure')),
    detail     TEXT,
    latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX provider_event_time_idx ON provider_event (occurred_at DESC);

CREATE TABLE spend_ledger (
    id                 BIGSERIAL PRIMARY KEY,
    run_id             TEXT          REFERENCES run(id) ON DELETE CASCADE,
    provider           TEXT          NOT NULL,
    model              TEXT          NOT NULL,
    estimated_cost_usd NUMERIC(12,6) NOT NULL CHECK (estimated_cost_usd >= 0),
    actual_cost_usd    NUMERIC(12,6) CHECK (actual_cost_usd IS NULL OR actual_cost_usd >= 0),
    tokens_in          INTEGER       NOT NULL DEFAULT 0 CHECK (tokens_in >= 0),
    tokens_out         INTEGER       NOT NULL DEFAULT 0 CHECK (tokens_out >= 0),
    cache_hit          BOOLEAN       NOT NULL DEFAULT FALSE,
    occurred_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX spend_ledger_run_idx ON spend_ledger (run_id);
COMMENT ON COLUMN spend_ledger.estimated_cost_usd IS
  'Worst-case price taken BEFORE the call fires. Not nullable, because control requires it (ADR-0007).';

CREATE TABLE eval_run (
    id         BIGSERIAL PRIMARY KEY,
    suite      TEXT        NOT NULL CHECK (suite IN ('core','probe')),
    git_sha    TEXT        NOT NULL,
    metrics    JSONB       NOT NULL,
    passed     BOOLEAN     NOT NULL,
    warned     BOOLEAN     NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX eval_run_suite_time_idx ON eval_run (suite, started_at DESC);
COMMENT ON COLUMN eval_run.warned IS
  'The probe suite is EXPECTED to warn on every run. A change in its result requires explanation.';
