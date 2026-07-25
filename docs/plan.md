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

### In progress quality baseline
- Focused tests exist for community moderation and notifications inbox/read actions.
- Lint and Django checks are integrated into regular workflow.

## Remaining high-value work

### 1. Reminder delivery path
- Add a management command for scheduled reminder dispatch.
- Integrate NotificationEvent generation and email send behavior.
- Add tests for reminder candidate selection and delivery status changes.

### 2. End-to-end hardening
- Add smoke tests for signup, join, approve/reject, notifications, and workout logging paths.
- Add deployment runbook steps for migrate, ensure_superuser, seed policy, and health checks.

## Suggested next implementation step
Implement reminder delivery next with a scheduled management command and NotificationEvent delivery transitions. This will connect assignment/guidance activity to proactive user engagement.
