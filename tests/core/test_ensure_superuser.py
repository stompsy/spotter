import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_ensure_superuser_creates_one_when_missing(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "deploy_admin")
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "deploy_admin@example.com")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "supersecret123")

    call_command("ensure_superuser")

    user_model = get_user_model()
    admin = user_model.objects.get(username="deploy_admin")
    assert admin.email == "deploy_admin@example.com"
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.check_password("supersecret123")


@pytest.mark.django_db
def test_ensure_superuser_skips_if_one_exists(monkeypatch):
    user_model = get_user_model()
    existing = user_model.objects.create_superuser(
        username="existing_admin",
        email="existing_admin@example.com",
        password="pw",
    )

    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_EMAIL", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)

    call_command("ensure_superuser")

    assert user_model.objects.filter(is_superuser=True).count() == 1
    assert user_model.objects.get(pk=existing.pk).username == "existing_admin"


@pytest.mark.django_db
def test_ensure_superuser_errors_without_credentials(monkeypatch):
    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_EMAIL", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)

    with pytest.raises(CommandError):
        call_command("ensure_superuser")
