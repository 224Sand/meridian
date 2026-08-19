# Requirements Traceability Matrix

**Version:** 1.0 · **Owner:** Business Analyst · **Date:** 2026-08-20
**Gate:** enforced by `scripts/check-docs.mjs` — a requirement without a story
and a test fails the build (charter §11).

---

## How to read the Status column

At the close of Sprint 0 no product code exists, so no product test exists
either. The **Test** column names the test that will assert the requirement and
the **Status** column states the truth about it today. Nothing here is claimed
as done that is not done. This column is rendered verbatim on the public
delivery surface (AC-002).

`Planned` · specified, not yet built  ·  `Building` · in the active sprint  ·  `Done` · implemented, test green in CI

---

| ID | Requirement | Story | Test | Sprint | Status |
|---|---|---|---|---|---|
| VIS-001 | Reads as production-grade engineering to a senior reviewer | S6-REVIEW | `e2e/reviewer_journey.spec.ts` | 6 | Planned |
| PR-001 | Named-role PDLC with explicit sign-off gates | S0-01 | `check-docs.mjs` (artifact + gate presence) | 0 | Done |
| AC-002 | Every PDLC claim verifiable; no simulated delivery metrics | S0-01, S5-DELIV | `check-docs.mjs`, `test_delivery_reads_live_github` | 0,5 | Done (gate) |
| AC-001 | Experience layer separated from agent runtime | S0-04 | `test_contract_bff_to_runtime` | 0,2 | Done (design) |
| NFR-001 | Effort directed at delivery, not deliberation | S0-01 | Sprint velocity vs. committed points | 0 | Done |
| NFR-002 | Zero infrastructure cost | S0-04 | `test_no_paid_service_in_deploy_manifest` | 0,6 | Done (design) |
| NFR-003 | First meaningful paint under 2.5s on cold 4G | S4-PERF | Lighthouse budget assertion in CI | 4 | Planned |
| NFR-004 | Public endpoint survives untrusted traffic without unbounded cost | S2-GUARD | `test_rate_limiter_denies_when_store_unreachable` | 2 | Planned |
| NFR-005 | Runtime holds no persistent local state | S1-DATA | `test_no_local_filesystem_writes` | 1 | Planned |
| DR-001 | Visual quality meets apple.com product-page standard | S4-UX | `e2e/motion_and_reduced_motion.spec.ts` | 4 | Planned |
| FR-001 | Product name changeable without code changes | S0-06 | `check-config.mjs` slug-derivation invariant | 0 | Done |
| SD-001 | Deliverable is a working product, not a portfolio listing | S0-03 | PO acceptance at each sprint review | 0 | Done |
| SD-002 | Synthetic data only; no real customer data | S1-SEED | `test_seed_data_is_generated_not_imported` | 1 | Planned |
| SD-003 | No job-application or resume tooling | S0-03 | PRD §8 scope exclusion, reviewed at each gate | 0 | Done |
| SD-004 | Domain is agent reliability; incident triage is the workload | S0-03 | PO acceptance | 0 | Done |
| CR-001 | Resume content restrictions do not apply | S0-02 | BRD §7 scope statement | 0 | Done |
| INF-001 | HF Spaces runtime, Vercel experience layer | S0-05 | ADR-0003; `test_container_binds_7860` | 0,6 | Done (decision) |
| OPS-001 | Host disk reclamation authorised | S0-09 | Pre-build disk check recorded in sprint log | 0 | Done |
| BR-001 | Triage an incident, produce a hypothesis with cited evidence | S3-TRIAGE | `test_every_emitted_claim_carries_a_citation` | 2,3 | Planned |
| BR-002 | Demonstrate PDLC/SDLC/CI-CD/Agile/Scrum verifiably | S5-DELIV | `test_delivery_reads_live_github` | 5 | Planned |
| BR-003 | Continue operating when a provider fails or rate-limits | S2-ROUTER | `test_workflow_completes_when_first_provider_fails` | 2 | Planned |
| BR-004 | Refuse when evidence does not support an answer | S2-RAG | `test_unanswerable_questions_are_refused` | 2 | Planned |
| BR-005 | Record a full, inspectable execution trace per run | S3-TRACE | `test_span_tree_covers_every_node` | 2,3 | Planned |
| BR-006 | Block high-risk actions pending human approval | S2-GOV | `test_approval_node_has_no_outgoing_edges` | 2 | Planned |
| BR-007 | Attribute tokens and cost to each run | S2-SPEND | `test_spend_ledger_records_estimate_and_actual` | 2 | Planned |
| BR-008 | Retain session and cross-incident memory | S3-MEM | `test_memory_recall_within_session` | 3 | Planned |
| BR-009 | Evaluate quality against a fixed golden set | S2-EVAL | `test_golden_core_suite_passes` | 2 | Planned |
| BR-010 | Reduce redundant model calls via semantic caching | S2-CACHE | `test_semantic_cache_hit_on_paraphrase` | 2 | Planned |
| BR-011 | Present own architecture, decisions and delivery record | S5-ARCH | `e2e/architecture_and_delivery.spec.ts` | 5 | Planned |
| FR-002 | Simulated production estate, deterministically seeded | S1-SEED | `test_seed_is_reproducible_from_seed_value` | 1 | Planned |
| FR-003 | Incident feed on schedule and on demand | S1-FEED | `test_incident_fires_on_demand` | 1 | Planned |
| FR-004 | Live triage run streamed to the client | S3-STREAM | `test_sse_emits_node_events_in_order` | 3 | Planned |
| FR-005 | Cited evidence panel; unsupported claims marked | S3-CITE | `test_every_emitted_claim_carries_a_citation` | 3 | Planned |
| FR-006 | Explicit refusal on insufficient evidence | S2-RAG | `test_unanswerable_questions_are_refused` | 2 | Planned |
| FR-007 | Human approval gate; approval is terminal | S2-GOV | `test_approval_node_has_no_outgoing_edges` | 2 | Planned |
| FR-008 | Session memory, visible to the user | S3-MEM | `test_memory_panel_reflects_stored_items` | 3 | Planned |
| FR-009 | Postmortem drafting from a completed run | S3-RCA | `test_postmortem_cites_only_run_evidence` | 3 | Planned |
| FR-010 | Deterministic router with time-boxed provider disabling | S2-ROUTER | `test_rate_limited_provider_is_disabled_for_ttl_then_reenabled` | 2 | Planned |
| FR-011 | Visitor-triggered provider failure injection | S2-CHAOS | `test_chaos_injection_is_session_scoped` | 2 | Planned |
| FR-012 | Semantic cache with visible hit rate and spend avoided | S2-CACHE | `test_cache_key_includes_embedding_model` | 2 | Planned |
| FR-013 | Execution trace viewer | S3-TRACE | `e2e/trace_viewer.spec.ts` | 3 | Planned |
| FR-014 | Cost attribution and pre-flight spend guard | S2-SPEND | `test_live_call_refused_without_open_budget` | 2 | Planned |
| FR-015 | Evaluation harness over the golden set | S2-EVAL | `test_golden_core_suite_passes` | 2 | Planned |
| FR-016 | Known-limitation probe suite that warns every run | S2-EVAL | `test_probe_suite_reports_warning_not_failure` | 2 | Planned |
| FR-017 | Cinematic scroll-driven product narrative | S4-UX | `e2e/scroll_scene_progression.spec.ts` | 4 | Planned |
| FR-018 | Reduced-motion and mobile comprehension paths | S4-UX | `e2e/motion_and_reduced_motion.spec.ts` | 4 | Planned |
| FR-019 | Interactive architecture view | S5-ARCH | `e2e/architecture_and_delivery.spec.ts` | 5 | Planned |
| FR-020 | Live CI/CD status from the GitHub API | S5-DELIV | `test_delivery_reads_live_github` | 5 | Planned |
| FR-021 | Requirements traceability rendered publicly | S5-DELIV | `test_traceability_view_matches_matrix_file` | 5 | Planned |
| FR-022 | Sprint and velocity record from real commit history | S5-DELIV | `test_velocity_derived_from_commit_timestamps` | 5 | Planned |
| FR-023 | Decision records rendered with context and consequences | S5-DELIV | `test_all_adrs_render` | 5 | Planned |
| FR-024 | Postmortems for real defects hit during the build | S6-DELIV | `test_postmortems_render` | 6 | Planned |
| FR-025 | Change risk review workload on the same orchestration graph | S3-WORKLOAD | `test_both_workloads_share_one_graph` | 3 | Planned |

---

## Coverage summary

| Sprint | Requirements landing | Cumulative |
|---|---|---|
| 0 Inception | 13 | 13 / 52 |
| 1 Foundation | 4 | 17 / 52 |
| 2 Agent Core | 15 | 32 / 52 |
| 3 Console | 9 | 41 / 52 |
| 4 Experience | 4 | 45 / 52 |
| 5 Proof Surfaces | 8 | 53* |
| 6 Release | 2 | 52 / 52 |

\* Some requirements are satisfied across two sprints and are counted in each;
the denominator is unique requirements.

## Orphan check

Run `npm run check:docs`. It fails if any declared requirement is missing from
this table, if any row has an empty story or test, or if any listed artifact is
a stub. It warns if this table contains an ID that no declaring document
introduced.
