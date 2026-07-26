# Spotter Exercise Content Policy

## Purpose
This policy defines how exercise and training guidance content is sourced,
reviewed, and published in Spotter.

## Scope
This policy applies to:

- Exercise cards and instructions
- Workout templates and challenge content
- Imported candidate guidance from docs and web sources
- Linked media (images, video, diagrams)

## Source Acceptance Tiers

### Tier A: Structured datasets (preferred)
Use for canonical exercise names, categories, and non-copyrightable metadata.

Examples:

- Public-domain or open-license movement libraries
- Internally authored structured exercise catalogs

Requirements:

- License permits reuse
- License type and source URL are recorded
- Imported records remain review-gated before publish

### Tier B: Media and reference sources
Use for media candidates and attribution metadata only.

Examples:

- Licensed stock media
- Creator media with explicit reuse terms
- Partner-provided assets with written approval

Requirements:

- Asset-level rights are verified
- Attribution text is recorded where required
- Source media URLs and license notes are stored

### Tier C: Safety overlays
Use for safety checks and coaching considerations.

Examples:

- Public health and sports medicine references
- Authoritative training standards and caution guidance

Requirements:

- Source credibility is recorded
- Safety notes are rewritten in Spotter language
- Medical claims are not added

## Prohibited Content
Do not ingest or publish:

- Verbatim copyrighted instruction text without permission
- Copyrighted images or videos without valid reuse rights
- Paywalled or ToS-restricted content copied into Spotter
- Clinical or diagnostic claims presented as medical advice
- Dangerous instructions that omit critical safety context

## Attribution Rules

- Store source URL and source name for each curated candidate.
- Store license name (for example, CC BY 4.0) before publication.
- If attribution is required, include it in metadata and render path.
- Keep authoring notes that identify where rewritten guidance came from.

## Media Rights Rules

- Every media item must include license or rights evidence.
- Unknown-license media cannot move to published state.
- Third-party logos and trademarked overlays should be removed unless licensed.
- Replace questionable media with internally authored or verified alternatives.

## Publication Guardrails

- Candidate status must pass workflow: draft -> needs_review -> approved -> published.
- Publishing requires approved source and non-empty license metadata.
- Publishing also requires candidate metadata keys:
	- source_name
	- source_url
	- attribution_text
	- media_rights_confirmed = true
	- content_rewritten = true
	- safety_reviewed = true
- Reviewer decision events must be preserved in immutable audit history.

## Guidance Disclaimer Pattern
All user-facing exercise guidance must include this disclaimer text pattern:

"Exercise guidance in Spotter is educational only and is not medical advice.
Consult a qualified professional before starting or changing training, especially
if you have injuries, pain, or health conditions."

## Admin Review Checklist
Before publishing or approving any candidate, confirm all items below.

1. Source category is acceptable (Tier A, B, or C).
2. Source URL/path and source name are present.
3. License metadata is present and valid for intended usage.
4. Content is rewritten; no prohibited verbatim copying.
5. Safety cues, regressions, and common mistakes are included where needed.
6. No medical diagnosis, treatment, or injury cure claims are present.
7. Required attribution fields are recorded.
8. Media rights are verified for each attached asset.
9. Reviewer decision reason is documented.
10. Candidate transitions follow workflow and publish gate requirements.
