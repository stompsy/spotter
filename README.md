# Spotter

Django community workout platform MVP scaffold.

## Git Workflow Standards

This repository uses a trunk-based workflow with short-lived feature branches and pull requests.

- Base branch: `main`
- Branch naming: `feat/<name>`, `fix/<name>`, `chore/<name>`
- Commit style: Conventional Commits (`feat:`, `fix:`, `chore:`, etc.)
- Merge policy: PR merge after CI passes and review is complete

Recommended flow for each feature:

1. `git checkout main && git pull`
2. `git checkout -b feat/<feature-name>`
3. Implement changes
4. Run validation: `make check` and `npm run tailwind:build` if relevant
5. Commit with conventional messages
6. Push branch and open PR
7. Merge PR to `main` after checks and review

## CI And Quality Gates

GitHub Actions CI runs on pull requests and pushes to `main` and validates:

- Ruff lint
- Django checks
- Migration drift (`makemigrations --check --dry-run`)
- Pytest
- Tailwind production build

Local verification commands:

- `make lint`
- `make manage-check`
- `make migrations-check`
- `make test`
- `make check`

## Semantic Releases

Automated semantic releases are configured with `python-semantic-release`.

- Release workflow triggers after CI succeeds on `main` (or manually)
- Version bump is determined from conventional commits
- Changelog is updated automatically
- Git tags use `v<version>`

For release automation to work in GitHub:

- Keep commit and PR titles conventional
- Protect `main` and require CI checks before merge
- Ensure Actions have write permissions to contents

## Environment Configuration

This project loads secrets and settings from `.env` (via `python-dotenv`).

1. Copy `.env.example` to `.env`
2. Set real values for secrets and database credentials

PostgreSQL is the default for development and production.

Use SQLite only when explicitly needed by setting:

- `USE_SQLITE=1`

## Static Asset Policy

Tailwind source input is versioned and required by CI:

- `assets/css/input.css` is committed source-of-truth for Tailwind compilation.
- `src/static/css/output.css` is the generated build artifact used by the app.

Rebuild CSS when frontend classes change:

- `npm run tailwind:build`

## Local PostgreSQL Dev Flow

Start database (Docker):

`docker compose up -d db`

Default local port in `.env.example` is `5433` to avoid conflicts with existing local Postgres installations.

Run migrations against Postgres:

`make migrate-dev`

Seed dev data:

`make seed-dev`

## DBGate Database Viewer

DBGate is included in `docker-compose.yml` and preconfigured to connect to the local Postgres service.

Start DB and DBGate:

`make dbgate-up`

Open DBGate:

`http://localhost:3000`

Stop DB and DBGate:

`make db-down`

## Manual Superuser Creation

When you want to choose credentials interactively:

`make createsuperuser`

If your environment has multiple database configs, run it with the same Postgres env vars used by your app.

## Deployment Superuser Setup

For Railway/Render style deploys, set these environment variables:

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD`

Then run this command as part of your release phase after migrations:

`make ensure-superuser`

The command is idempotent:

- If a superuser already exists, it does nothing.
- If no superuser exists, it creates or promotes the configured username.

## Reminder Delivery Command

Dispatch due workout reminders into `NotificationEvent` rows:

- `python manage.py send_reminders`

Options:

- `--days-ahead N`: include assignments starting up to N days ahead
- `--dry-run`: preview candidates without writing notifications

## Exercise Reviewer Onboarding

Use the reviewer bootstrap command to provision candidate-curation reviewers.

Create or update the `Exercise Reviewers` group and ensure it has the
`review_exercisecandidate` permission:

- `python manage.py bootstrap_exercise_reviewers`

Assign one or more existing users to the reviewer group:

- `python manage.py bootstrap_exercise_reviewers --usernames alice bob`

Production-style release flow (after migrations):

1. `python manage.py migrate --noinput`
2. `python manage.py bootstrap_exercise_reviewers --usernames <reviewer_username>`

Notes:

- The command is idempotent and safe to rerun.
- If any provided username does not exist, the command exits with an error.
