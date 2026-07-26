from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.workouts.models import (
    CurationStatus,
    ExerciseCandidate,
    ExerciseSource,
    ExerciseSourceType,
)


@pytest.mark.django_db
def test_ingest_exercise_candidates_creates_source_and_draft_candidates(tmp_path):
    source_file = tmp_path / "Lunges.txt"
    source_file.write_text(
        "\n".join(
            [
                "30 Forward Lunges (15 each leg)",
                "20 Right Side Lunges",
                "20 Left Side Lunges",
                "30 Reverse Lunges (15 each leg)",
                "Switch Lunges: Do as many you can",
                "http://beta.active.com/fitness/Articles/Master-the-Plank.htm",
            ]
        ),
        encoding="utf-8",
    )

    call_command("ingest_exercise_candidates", source_file=str(source_file))

    source = ExerciseSource.objects.get(location=str(source_file))
    assert source.source_type == ExerciseSourceType.DOCUMENT

    normalized = set(
        ExerciseCandidate.objects.filter(source=source).values_list(
            "normalized_name",
            flat=True,
        )
    )
    assert normalized == {
        "forward lunge",
        "side lunge",
        "reverse lunge",
        "switch lunge",
        "plank",
    }

    assert (
        ExerciseCandidate.objects.filter(
            source=source,
            status=CurationStatus.DRAFT,
        ).count()
        == 5
    )


@pytest.mark.django_db
def test_ingest_exercise_candidates_is_idempotent_for_normalized_names(tmp_path):
    source_file = tmp_path / "Lunges.txt"
    source_file.write_text(
        "\n".join(
            [
                "Forward Lunges",
                "Forward Lunges",
                "Left Side Lunges",
                "Right Side Lunges",
            ]
        ),
        encoding="utf-8",
    )

    call_command("ingest_exercise_candidates", source_file=str(source_file))
    call_command("ingest_exercise_candidates", source_file=str(source_file))

    source = ExerciseSource.objects.get(location=str(source_file))
    candidates = ExerciseCandidate.objects.filter(source=source)
    assert candidates.count() == 2
    assert set(candidates.values_list("normalized_name", flat=True)) == {
        "forward lunge",
        "side lunge",
    }
