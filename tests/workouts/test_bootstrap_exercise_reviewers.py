import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_bootstrap_exercise_reviewers_creates_group_with_permission():
    call_command("bootstrap_exercise_reviewers")

    group = Group.objects.get(name="Exercise Reviewers")
    permission = Permission.objects.get(codename="review_exercisecandidate")
    assert group.permissions.filter(id=permission.id).exists()


@pytest.mark.django_db
def test_bootstrap_exercise_reviewers_is_idempotent():
    call_command("bootstrap_exercise_reviewers")
    call_command("bootstrap_exercise_reviewers")

    group = Group.objects.get(name="Exercise Reviewers")
    permission = Permission.objects.get(codename="review_exercisecandidate")
    assert Group.objects.filter(name="Exercise Reviewers").count() == 1
    assert group.permissions.filter(id=permission.id).count() == 1


@pytest.mark.django_db
def test_bootstrap_exercise_reviewers_assigns_users_by_username():
    user_model = get_user_model()
    first = user_model.objects.create_user(
        username="reviewer_one",
        email="reviewer_one@example.com",
        password="pw",
    )
    second = user_model.objects.create_user(
        username="reviewer_two",
        email="reviewer_two@example.com",
        password="pw",
    )

    call_command("bootstrap_exercise_reviewers", usernames=[first.username, second.username])

    group = Group.objects.get(name="Exercise Reviewers")
    assert group.user_set.filter(id=first.id).exists()
    assert group.user_set.filter(id=second.id).exists()


@pytest.mark.django_db
def test_bootstrap_exercise_reviewers_errors_for_unknown_username():
    with pytest.raises(CommandError):
        call_command("bootstrap_exercise_reviewers", usernames=["missing-user"])
