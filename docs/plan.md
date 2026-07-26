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

## Phased roadmap

### Phase 0 - Product Guardrails and Data Governance
1. Define content and licensing policy first so implementation is legally safe and maintainable.
2. Create content policy and admin checklist:
- accepted source types
- prohibited content ingestion (verbatim copyrighted text/images)
- attribution requirements
- media rights requirements
3. Add exercise guidance disclaimer pattern (informational, not medical advice).

### Phase 1 - Domain Model Expansion (Foundational)
1. Extend exercise taxonomy beyond current category enum.
2. Add normalized exercise metadata fields:
- movement type
- body areas
- difficulty level
- equipment requirements
- contraindications and safety notes
- setup, execution steps, common mistakes, coaching cues
- default prescription ranges by goal
3. Add media model support (uploads, external URL, license metadata).
4. Add plan-type and duration semantics:
- single-session, challenge, program
- short, medium, long sessions
- challenge duration and focus area
5. Add challenge-day structure model.
6. Add optional phased periodization model.

### Phase 2 - Exercise Card Authoring and Discovery UX
1. Upgrade exercise management UI for rich card creation/editing and moderation state.
2. Render exercise cards with image/media, body-area badges, safe-form instructions, common prescriptions, and caution notes.
3. Add search/filter/sort by movement type, body area, equipment, level, and duration fit.
4. Add copy-safe challenge presets (Abs 30-day, Lunge 30-day first).

### Phase 3 - Plan Builder and Challenge Templates
1. Build guided plan composer with reusable cards and day templates.
2. Support short/medium/long templates with suggestion logic.
3. Add challenge wizard (focus area, duration, progression, checkpoints).
4. Support split completion behavior for daily targets.
5. Add validation rules for balance, recovery spacing, and warm-up/cooldown coverage.

### Phase 4 - Calendar System (Full View Set in First Release)
1. Introduce schedule layer from assignments and challenge days.
2. Build main user calendar views:
- daily
- rolling 3-day
- weekly
- monthly
- yearly
3. Add day states: planned, partial, complete, missed, rest.
4. Link calendar cells to workouts, logs, notes, and challenge progress.
5. Add coach/community overlays where permissions allow.

### Phase 5 - Progress Analytics and Insight Safety
1. Add challenge KPIs:
- adherence
- streaks
- baseline vs current
- checkpoint deltas and percentages
2. Add body-area and movement-type volume summaries.
3. Add load-safety alerts for abrupt spikes/repeated high-RPE streaks.
4. Keep insights educational and non-diagnostic.

### Phase 6 - Internet Exercise Intelligence Pipeline and Curation
1. Build source registry model for provenance and approval.
2. Define source tiers:
- Tier A structured exercise datasets
- Tier B media sources with asset-level licensing
- Tier C safety overlays
3. Add ingestion adapters:
- dataset adapter
- media adapter
- manual editor adapter
4. Add curation workflow states:
- draft
- needs_review
- approved
- published
- deprecated
5. Add content quality checks:
- duplicate detection
- instruction completeness score
- safety completeness score
6. Build docs import tooling (start with Lunges.txt).
7. Add implementation-time PDF extraction toolkit:
- pypdf first pass
- pdfplumber fallback
- OCR fallback (pypdfium2 plus pytesseract)
- normalization and candidate extraction
- low-confidence review queue
8. Build first curated bundles:
- warm-up
- calisthenics
- cooldown
- 30-day abs and 30-day lunge challenge seeds
9. Implement dedicated PDF extraction and internet-lookup subsystem:
- parser routing
- candidate mining and confidence scoring
- curation gates and copy-safety checks
- persistence schema for runs/pages/candidates/references/decisions
- verification targets

### Phase 7 - Permissions, Safety, and Operations
1. Add role-aware publication permissions.
2. Add moderation queues for flagged media and unsafe edits.
3. Add audit events for publication and major changes.
4. Add background jobs for schedule materialization and reminder fan-out.

### Phase 8 - Delivery Strategy (Incremental)
1. Slice A: exercise taxonomy plus rich card UI plus filters.
2. Slice B: challenge models plus Abs/Lunge presets.
3. Slice C: calendar daily/3-day/weekly/monthly/yearly.
4. Slice D: advanced analytics plus safeguards plus curation pipeline.
5. Keep migrations backward-compatible and feature-flag new UI as needed.

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
