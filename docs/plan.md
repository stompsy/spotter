# Spotter Plan And Status

## Why this file exists
This is the visible implementation roadmap and status tracker in the workspace.

## Current status summary

### Completed baseline
- Foundation scaffold is in place: Django project structure, custom user model, PostgreSQL-first configuration, Tailwind pipeline, browser reload wiring.
- Community browse and detail flows are implemented.
- Join request lifecycle is implemented for submit, approve, and reject.
- Moderator permissions and moderation records for join decisions are implemented.
- Notification events are generated for join request submission and join decision outcomes.
- Notifications inbox UI exists, including unread/read state and mark-read actions.
- Private community invitation creation and acceptance flows are implemented.
- Workout plans first slice is implemented: list/create/detail, add plan items, and plan assignment.
- Workout domain expansion is implemented with exercise create/edit/archive, plan edit/clone/publish controls, and assignment lifecycle actions (pause/resume/end) with history fields.
- Guidance moderation workflow is implemented with draft creation, submit-for-review, moderation decisions, moderation history, and publish controls.
- Reminder delivery path is implemented with scheduled dispatch, NotificationEvent generation, email send attempts, and sent/failed delivery status transitions.
- Workout logging UI first slice is implemented with authenticated list/create flow, per-user visibility, and assignment-linked plan selection.
- Progress insights, filters, trend charting, compare-period indicators, and CSV exports are implemented with focused tests.

### Quality baseline
- Lint and Django checks are integrated into regular workflow.
- Smoke coverage exists for signup, moderation flow, notifications flow, and workout assignment/logging.
- Deployment runbook and Makefile release wrappers are in place.

### Current implementation status
- Plan approved for implementation kickoff on 2026-07-25.
- Initial focus: Phase 1 foundation plus Phase 6 ingestion scaffolding in thin vertical slices.
- Slice 1 merged: source registry, exercise candidates, ingestion command, admin integration, tests.
- Slice 2 merged: extraction run/page parser-routing scaffolding, command logging, admin visibility, and coverage tests.
- Slice 3 merged: candidate review action endpoint and curation status transition guardrails with tests.
- Slice 4 merged: reviewer decision metadata and publish prerequisites (approved source plus license metadata) with tests.
- Slice 5 merged: candidate review queue UI with status/confidence filters and filter-preserving review actions.
- Slice 6 merged: immutable candidate decision audit trail with admin visibility, UI audit feed, and tests.
- Slice 7 merged: reviewer-only permission gate for candidate curation actions with authorization coverage tests.
- Slice 8 merged: permission-based reviewer gate using explicit ExerciseCandidate review permission and test coverage updates.
- Slice 9 merged: bootstrap command for Exercise Reviewers group provisioning and optional user assignment with command tests.
- Slice 10 merged: reviewer onboarding runbook in README with local and production command examples.
- Slice 11 merged: Phase 0 content policy, admin review checklist, and reusable guidance disclaimer pattern.
- Slice 12 merged: publish-time metadata enforcement for attribution and safety guardrails with tests.
- Slice 13 merged: admin form-level publish validation and reviewer guidance help text for required metadata.
- Slice 14 merged: structured metadata helper fields in admin for publish requirements with form round-trip tests.
- Slice 15 merged: in-app candidate review metadata helper parity with structured field persistence and coverage tests.
- Slice 16 merged: reviewer guardrail feedback with inline publish requirement gaps and specific publish error messaging.
- Slice 17 merged: publish-readiness queue filtering, per-requirement reviewer confirmation audit metadata, and in-form policy help panel.
- Slice 18 merged: Phase 1 taxonomy expansion with movement type, body area, difficulty, and equipment requirement fields plus migration/UI/test coverage.
- Slice 19 merged: Phase 1 normalized metadata expansion with safety/instruction authoring fields and default prescription ranges by goal.
- Slice 20 merged: Phase 1 media support with ExerciseMedia model, upload/external URL validation, license metadata, and UI/admin/test coverage.
- Slice 21 merged: Phase 1 workout plan semantics with plan type, duration band, and challenge-specific duration/focus fields plus validation and UI/test coverage.
- Slice 22 merged: Phase 1 challenge-day structure model with day numbering guardrails, optional plan-item day linkage, detail view visibility, and test coverage.
- Slice 23 merged: Phase 1 optional phased periodization model for program plans with week-range guardrails, admin visibility, detail rendering, and test coverage.
- Slice 24 merged: Phase 1 workout-role category taxonomy expansion with broader exercise categories, backward-compatible choice preservation, migration, and flow test coverage.
- Slice 25 merged: Phase 2 exercise library UI upgrade with richer exercise cards, grouped authoring form sections, clearer library state badges, and page-render coverage.
- Slice 26 merged: Phase 2 discovery-ready exercise cards with stronger body-area and difficulty badges, highlighted caution cues, safe-form instruction labeling, and richer media attribution display.
- Slice 27 merged: Phase 2 exercise library search, filter, and sort with duration-fit metadata, queryset controls, UI filter bar, and focused list behavior coverage.
- Slice 28 merged: Phase 2 copy-safe challenge presets with one-click 30-day core and lunge templates, generated challenge days and linked items, and preset creation coverage.
- Slice 29 merged: Phase 3 guided plan composer starter templates with reusable short/medium/long insertions, challenge-day starter support, and focused composer workflow coverage.
- Slice 30 merged: Phase 3 adaptive template suggestions with inventory-aware short/medium/long recommendation logic and guided composer suggestion coverage tests.
- Slice 31 merged: Phase 3 challenge wizard with focus-area, duration, progression style, checkpoint cadence inputs, scaffolded challenge-day generation, and wizard behavior tests.
- Slice 32 merged: Phase 3 split completion behavior with per-day partial logging, cumulative target progress states, and challenge completion flow coverage.
- Slice 33 merged: Phase 3 challenge validation rules for balance, recovery spacing, and warm-up/cooldown coverage with publish-time guardrails and validation feedback tests.
- Slice 34 merged: Phase 4 schedule layer preview sourced from assignments and challenge-day sequencing with detail-view visibility and coverage tests.
- Slice 35 merged: Phase 4 calendar views (daily, rolling 3-day, weekly, monthly, yearly) backed by assignment/challenge schedule expansion and view coverage tests.

## Phased roadmap

Progress notation used below:
- [DONE] = delivered and merged
- [IN PROGRESS] = partially delivered in merged slices
- [PENDING] = not yet started

### Phase 0 - Product Guardrails and Data Governance
1. [DONE] ~~Define content and licensing policy first so implementation is legally safe and maintainable.~~
2. [DONE] ~~Create content policy and admin checklist:~~
- accepted source types
- prohibited content ingestion (verbatim copyrighted text/images)
- attribution requirements
- media rights requirements
3. [DONE] ~~Add exercise guidance disclaimer pattern (informational, not medical advice).~~

### Phase 1 - Domain Model Expansion (Foundational)
1. [DONE] ~~Extend exercise taxonomy beyond current category enum.~~
2. [DONE] ~~Add normalized exercise metadata fields:~~
- [DONE] movement type
- [DONE] body areas
- [DONE] difficulty level
- [DONE] equipment requirements
- [DONE] contraindications and safety notes
- [DONE] setup, execution steps, common mistakes, coaching cues
- [DONE] default prescription ranges by goal
3. [DONE] ~~Add media model support (uploads, external URL, license metadata).~~
4. [DONE] ~~Add plan-type and duration semantics:~~
- ~~single-session, challenge, program~~
- ~~short, medium, long sessions~~
- ~~challenge duration and focus area~~
5. [DONE] ~~Add challenge-day structure model.~~
6. [DONE] ~~Add optional phased periodization model.~~

### Phase 2 - Exercise Card Authoring and Discovery UX
1. [DONE] ~~Upgrade exercise management UI for rich card creation/editing and moderation state.~~
2. [DONE] ~~Render exercise cards with image/media, body-area badges, safe-form instructions, common prescriptions, and caution notes.~~
3. [DONE] ~~Add search/filter/sort by movement type, body area, equipment, level, and duration fit.~~
4. [DONE] ~~Add copy-safe challenge presets (Abs 30-day, Lunge 30-day first).~~

### Phase 3 - Plan Builder and Challenge Templates
1. [DONE] ~~Build guided plan composer with reusable cards and day templates.~~
2. [DONE] ~~Support short/medium/long templates with suggestion logic.~~
3. [DONE] ~~Add challenge wizard (focus area, duration, progression, checkpoints).~~
4. [DONE] ~~Support split completion behavior for daily targets.~~
5. [DONE] ~~Add validation rules for balance, recovery spacing, and warm-up/cooldown coverage.~~

### Phase 4 - Calendar System (Full View Set in First Release)
1. [DONE] ~~Introduce schedule layer from assignments and challenge days.~~
2. [DONE] ~~Build main user calendar views:~~
- daily
- rolling 3-day
- weekly
- monthly
- yearly
3. [PENDING] Add day states: planned, partial, complete, missed, rest.
4. [PENDING] Link calendar cells to workouts, logs, notes, and challenge progress.
5. [PENDING] Add coach/community overlays where permissions allow.

### Phase 5 - Progress Analytics and Insight Safety
1. [PENDING] Add challenge KPIs:
- adherence
- streaks
- baseline vs current
- checkpoint deltas and percentages
2. [PENDING] Add body-area and movement-type volume summaries.
3. [PENDING] Add load-safety alerts for abrupt spikes/repeated high-RPE streaks.
4. [PENDING] Keep insights educational and non-diagnostic.

### Phase 6 - Internet Exercise Intelligence Pipeline and Curation
1. [DONE] ~~Build source registry model for provenance and approval.~~
2. [DONE] ~~Define source tiers:~~
- Tier A structured exercise datasets
- Tier B media sources with asset-level licensing
- Tier C safety overlays
3. [IN PROGRESS] Add ingestion adapters:
- dataset adapter
- media adapter
- manual editor adapter
4. [DONE] ~~Add curation workflow states:~~
- draft
- needs_review
- approved
- published
- deprecated
5. [IN PROGRESS] Add content quality checks:
- duplicate detection
- instruction completeness score
- safety completeness score
6. [IN PROGRESS] Build docs import tooling (start with Lunges.txt).
7. [IN PROGRESS] Add implementation-time PDF extraction toolkit:
- pypdf first pass
- pdfplumber fallback
- OCR fallback (pypdfium2 plus pytesseract)
- normalization and candidate extraction
- low-confidence review queue
8. [PENDING] Build first curated bundles:
- warm-up
- calisthenics
- cooldown
- 30-day abs and 30-day lunge challenge seeds
9. [IN PROGRESS] Implement dedicated PDF extraction and internet-lookup subsystem:
- parser routing
- candidate mining and confidence scoring
- curation gates and copy-safety checks
- persistence schema for runs/pages/candidates/references/decisions
- verification targets

### Phase 7 - Permissions, Safety, and Operations
1. [IN PROGRESS] Add role-aware publication permissions.
2. [PENDING] Add moderation queues for flagged media and unsafe edits.
3. [IN PROGRESS] Add audit events for publication and major changes.
4. [PENDING] Add background jobs for schedule materialization and reminder fan-out.

### Phase 8 - Delivery Strategy (Incremental)
1. [PENDING] Slice A: exercise taxonomy plus rich card UI plus filters.
2. [PENDING] Slice B: challenge models plus Abs/Lunge presets.
3. [PENDING] Slice C: calendar daily/3-day/weekly/monthly/yearly.
4. [PENDING] Slice D: advanced analytics plus safeguards plus curation pipeline.
5. [IN PROGRESS] Keep migrations backward-compatible and feature-flag new UI as needed.

## Appendix A - PDF Exercise Extraction And Internet Lookup (Phase 6 detailed design)

### Objective
Extract candidate exercise names and plan-structure signals from docs PDFs, then enrich with curated internet research for safe instructions and media metadata.

### Inputs
- docs/30-Day-Abs-Challenge-Calendar.pdf
- docs/30-Day-Lunge-Challenge-Calendar.pdf
- docs/Tri-Phase Workout.pdf
- docs/marsoc-training-guide-2018-1.pdf
- docs/Lunges.txt

### Extraction pipeline (ordered fallbacks)
1. Classify pages as text-based vs image-based.
2. Parser path:
- pypdf first
- pdfplumber fallback for low-yield pages
3. OCR path:
- page render via pypdfium2
- OCR via pytesseract
4. Recovery and resilience:
- per-page method, duration, and yield logging
- extracted/partial/failed status

### Detection and scoring
1. Normalize text, remove repeated headers/footers/page numbers.
2. Segment likely structures (days/weeks/phases/list items/rep-set directives).
3. Extract candidate exercise names with pattern rules and synonym maps.
4. Suppress false positives from legal/footer/marketing text.
5. Score confidence by extraction quality, context, lexical match, and frequency.
6. Thresholds:
- high >= 0.85
- medium 0.60-0.84
- low < 0.60

### Internet enrichment workflow
1. Query normalized names with movement type and safety cues.
2. Prioritize reusable-license sources with attribution clarity.
3. Capture enrichment fields:
- canonical name, aliases, movement type, body areas, equipment, level
- setup/execution/breathing/common mistakes/regressions/progressions
- media candidate URLs, license, attribution
4. Publish only internally authored rewritten instructions.

### Output schema
- ExtractionRun
- ExtractionPage
- ExerciseCandidate
- PlanSignalCandidate
- SourceReference
- CurationDecision

### Verification checklist
1. Extraction quality: >= 90 percent non-empty page outputs after fallback.
2. Candidate quality: high-confidence precision >= 0.9 on sample.
3. Recall: known Lunges.txt terms recovered at 100 percent.
4. Curation safety: published records require source + license metadata.
5. Regression tests: parser routing, normalization, scoring thresholds, end-to-end extraction paths.
