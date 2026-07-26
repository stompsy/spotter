# Deployment Runbook

This runbook defines the minimum deploy sequence for Spotter environments.

## Preconditions

- Required environment variables are configured.
- Database is reachable from the runtime environment.
- Application image/build has completed successfully.

## Required Environment Variables

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG` (set to `false` in production)
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DATABASE_ENGINE`
- `DATABASE_NAME`
- `DATABASE_USER`
- `DATABASE_PASSWORD`
- `DATABASE_HOST`
- `DATABASE_PORT`
- `DEFAULT_FROM_EMAIL`
- `EMAIL_BACKEND`

For non-interactive superuser bootstrapping:

- `DJANGO_SUPERUSER_USERNAME`
- `DJANGO_SUPERUSER_EMAIL`
- `DJANGO_SUPERUSER_PASSWORD`

## Release Sequence

Run these steps in order on each deployment:

1. Apply migrations.
2. Ensure a superuser exists.
3. Optionally seed demo data in non-production environments.
4. Run Django health checks.
5. Start application process.

## Commands

### 1) Migrate

```bash
python manage.py migrate --noinput
```

### 2) Ensure Superuser

```bash
python manage.py ensure_superuser
```

Expected behavior:

- If any superuser already exists, command exits without changes.
- If not, command creates or promotes the configured user.

### 3) Seed Policy

Production:

- Do not run `seed_demo`.

Staging or local demo environments:

```bash
python manage.py seed_demo
```

### 4) Health Checks

```bash
python manage.py check --deploy
```

If your platform cannot satisfy all `--deploy` checks yet, also run:

```bash
python manage.py check
```

## Platform Examples

### Railway

Use a release command sequence in project settings:

```bash
python manage.py migrate --noinput && python manage.py ensure_superuser && python manage.py check --deploy
```

Recommended service variables:

- `DJANGO_ALLOWED_HOSTS` should include the Railway service domain.
- `DJANGO_CSRF_TRUSTED_ORIGINS` should include `https://<your-domain>`.

### Render

Set the web service start command to your WSGI server, and use pre-deploy command:

```bash
python manage.py migrate --noinput && python manage.py ensure_superuser && python manage.py check --deploy
```

For background reminders, configure a separate cron job service:

```bash
python manage.py send_reminders
```

### GitHub Actions + Self-Hosted/VM Deploy

Use a deploy job step before restart:

```yaml
- name: Migrate and health check
  run: |
    python manage.py migrate --noinput
    python manage.py ensure_superuser
    python manage.py check --deploy
```

If your deployment uses PM2/systemd, restart only after these commands succeed.

## Reminder Delivery Schedule

Set a scheduler/cron entry to dispatch reminders:

```bash
python manage.py send_reminders
```

Optional lookahead window:

```bash
python manage.py send_reminders --days-ahead 2
```

Dry-run validation:

```bash
python manage.py send_reminders --dry-run
```

## Rollback Notes

- If deployment fails before migrations, rollback application version only.
- If deployment fails after migrations, either:
  - deploy a forward-fix quickly, or
  - restore from backup and execute a tested DB rollback procedure.

## Post-Deploy Verification

- Home page loads.
- Login page loads.
- Community list loads for authenticated users.
- Notifications inbox opens for authenticated users.
- A manual `send_reminders --dry-run` completes successfully.
