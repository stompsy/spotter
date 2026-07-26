# Spotter MVP Plan And Status

## Why this file exists
The original plan lived in session memory and was not visible in the workspace tree. This file is the visible working copy for ongoing implementation.

## Current status summary

### Completed
- Foundation scaffold is in place: Django project structure, custom user model, PostgreSQL-first configuration, Tailwind pipeline, browser reload wiring.
- Community browse and detail flows are implemented.
- Join request lifecycle is implemented for submit, approve, and reject.
- Moderator permissions and moderation records for join decisions are implemented.
- Notification events are generated for join request submission and join decision outcomes.
- Notifications inbox UI exists, including unread/read state and mark-read actions.
- Private community invitation creation and acceptance flows are implemented.
- Workout plans first slice is implemented: list/create/detail, add plan items, and plan assignment.
- Workout routes, templates, and focused tests are in place for the first slice.
- Workout domain expansion is implemented with exercise create/edit/archive, plan edit/clone/publish controls, and assignment lifecycle actions (pause/resume/end) with history fields.
- Guidance moderation workflow is implemented with draft creation, submit-for-review, moderation decisions, moderation history, and publish controls.
- Guidance queue/list/detail UI and focused tests are in place for workflow transitions and permissions.
- Admin registrations are added for users and domain models.
- Dev seed command exists and is idempotent.
- Superuser guard command exists for deploy automation.
- Reminder delivery path is implemented with scheduled dispatch, NotificationEvent generation, email send attempts, and sent/failed delivery status transitions.
- Reminder dispatch tests cover candidate selection, duplicate prevention, dry-run mode, and delivery status changes.

### In progress quality baseline
- Focused tests exist for community moderation and notifications inbox/read actions.
- Lint and Django checks are integrated into regular workflow.
- A first end-to-end smoke journey test now exercises signup, join request review (approve/reject), notifications read flow, and workout logging persistence.
- A deployment runbook draft now documents migrate, ensure_superuser, seed policy, health checks, and reminder scheduling steps.
- Smoke coverage is now split into targeted scenarios (signup, community review, notifications, workout assignment/logging) for clearer CI diagnostics.
- Deployment runbook now includes platform-specific examples for Railway, Render, and GitHub Actions based deployments.
- Smoke coverage now includes login-to-protected-page verification and reminder dispatch dry-run plus delivery execution.
- Makefile release wrappers now mirror the deployment runbook sequence and reminder operational commands.

## Remaining high-value work

### 1. Next product increment selection
- Prioritize the next user-visible capability after MVP hardening (for example: workout logging UI flows or progress dashboards).
- Define acceptance tests first for the selected increment.

## Suggested next implementation step
Select the next product increment and start with acceptance-test scaffolding before implementing view/model changes.
