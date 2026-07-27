from __future__ import annotations

import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.workouts.models import (
    CurationStatus,
    ExerciseCandidate,
    ExerciseExtractionPage,
    ExerciseExtractionRun,
    ExerciseSource,
    ExerciseSourceType,
    ExtractionMethod,
    ExtractionPageStatus,
)


@pytest.mark.django_db
def test_evaluate_extraction_quality_records_verification_summary():
    source = ExerciseSource.objects.create(
        name="Verification source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/verification-source.txt",
    )
    run = ExerciseExtractionRun.objects.create(source=source)

    for idx in range(1, 11):
        ExerciseExtractionPage.objects.create(
            run=run,
            page_number=idx,
            extraction_method=ExtractionMethod.TEXT_FILE,
            status=ExtractionPageStatus.EXTRACTED,
            raw_text=f"Page {idx}",
            cleaned_text=f"Page {idx}",
            char_count=12,
        )

    ExerciseCandidate.objects.create(
        source=source,
        raw_name="Forward Lunge",
        normalized_name="forward lunge",
        status=CurationStatus.APPROVED,
        confidence=0.93,
    )
    ExerciseCandidate.objects.create(
        source=source,
        raw_name="Reverse Lunge",
        normalized_name="reverse lunge",
        status=CurationStatus.PUBLISHED,
        confidence=0.92,
    )

    call_command(
        "evaluate_extraction_quality",
        run_id=run.id,
        expected_candidate=["forward lunge", "reverse lunge"],
    )

    run.refresh_from_db()
    verification = run.summary["verification"]
    assert verification["pages_total"] == 10
    assert verification["pages_with_text"] == 10
    assert verification["non_empty_page_ratio"] == 1.0
    assert verification["non_empty_page_ratio_pass"] is True
    assert verification["high_confidence_candidate_count"] == 2
    assert verification["high_confidence_true_positives"] == 2
    assert verification["high_confidence_precision"] == 1.0
    assert verification["high_confidence_precision_pass"] is True


@pytest.mark.django_db
def test_evaluate_extraction_quality_uses_latest_run_for_source_location():
    source = ExerciseSource.objects.create(
        name="Latest source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/latest-source.txt",
    )
    older_run = ExerciseExtractionRun.objects.create(source=source)
    newer_run = ExerciseExtractionRun.objects.create(source=source)

    ExerciseExtractionPage.objects.create(
        run=older_run,
        page_number=1,
        extraction_method=ExtractionMethod.TEXT_FILE,
        status=ExtractionPageStatus.EXTRACTED,
        raw_text="Old page",
        cleaned_text="Old page",
        char_count=10,
    )
    ExerciseExtractionPage.objects.create(
        run=newer_run,
        page_number=1,
        extraction_method=ExtractionMethod.TEXT_FILE,
        status=ExtractionPageStatus.PARTIAL,
        raw_text="",
        cleaned_text="",
        char_count=0,
    )

    call_command("evaluate_extraction_quality", source_location=source.location)

    newer_run.refresh_from_db()
    assert "verification" in newer_run.summary
    older_run.refresh_from_db()
    assert "verification" not in older_run.summary


@pytest.mark.django_db
def test_evaluate_extraction_quality_errors_when_run_missing():
    with pytest.raises(CommandError):
        call_command("evaluate_extraction_quality", run_id=999999)


@pytest.mark.django_db
def test_evaluate_extraction_quality_reports_latest_run_per_source_leaderboard():
    source_pass = ExerciseSource.objects.create(
        name="Pass source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/pass-source.txt",
    )
    source_pending = ExerciseSource.objects.create(
        name="Pending source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/pending-source.txt",
    )
    source_fail = ExerciseSource.objects.create(
        name="Fail source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/fail-source.txt",
    )

    pass_run = ExerciseExtractionRun.objects.create(
        source=source_pass,
        summary={
            "verification": {
                "non_empty_page_ratio": 1.0,
                "high_confidence_precision": 1.0,
                "non_empty_page_ratio_pass": True,
                "high_confidence_precision_pass": True,
            }
        },
    )
    ExerciseExtractionRun.objects.create(source=source_pending, summary={})
    fail_run = ExerciseExtractionRun.objects.create(
        source=source_fail,
        summary={
            "verification": {
                "non_empty_page_ratio": 0.7,
                "high_confidence_precision": 0.5,
                "non_empty_page_ratio_pass": False,
                "high_confidence_precision_pass": False,
            }
        },
    )

    out = io.StringIO()
    call_command("evaluate_extraction_quality", report_by_source=True, stdout=out)
    output = out.getvalue()

    assert "Source verification leaderboard" in output
    assert f"[PASS] run={pass_run.id} source={source_pass.location}" in output
    assert f"[FAIL] run={fail_run.id} source={source_fail.location}" in output
    assert f"[PENDING] run=" in output


@pytest.mark.django_db
def test_evaluate_extraction_quality_reports_by_source_respects_limit():
    for idx in range(1, 4):
        source = ExerciseSource.objects.create(
            name=f"Source {idx}",
            source_type=ExerciseSourceType.DOCUMENT,
            location=f"docs/source-{idx}.txt",
        )
        ExerciseExtractionRun.objects.create(source=source, summary={})

    out = io.StringIO()
    call_command(
        "evaluate_extraction_quality",
        report_by_source=True,
        limit=2,
        stdout=out,
    )
    output_lines = [line for line in out.getvalue().splitlines() if line.startswith("[")]
    assert len(output_lines) == 2


@pytest.mark.django_db
def test_evaluate_extraction_quality_assert_benchmarks_pass_success():
    source = ExerciseSource.objects.create(
        name="Benchmark source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/benchmark-source.txt",
    )
    run = ExerciseExtractionRun.objects.create(
        source=source,
        summary={
            "verification": {
                "non_empty_page_ratio_pass": True,
                "high_confidence_precision_pass": True,
            }
        },
    )

    out = io.StringIO()
    call_command(
        "evaluate_extraction_quality",
        assert_benchmarks_pass=True,
        benchmark_source=[source.location],
        stdout=out,
    )
    output = out.getvalue()
    assert f"BENCHMARK PASS source={source.location} run={run.id}" in output
    assert "All benchmark sources satisfy verification targets." in output


@pytest.mark.django_db
def test_evaluate_extraction_quality_assert_benchmarks_pass_errors_on_failures():
    source_missing = "docs/missing-benchmark-source.txt"
    source_failing = ExerciseSource.objects.create(
        name="Benchmark failing source",
        source_type=ExerciseSourceType.DOCUMENT,
        location="docs/failing-benchmark-source.txt",
    )
    ExerciseExtractionRun.objects.create(
        source=source_failing,
        summary={
            "verification": {
                "non_empty_page_ratio_pass": True,
                "high_confidence_precision_pass": False,
            }
        },
    )

    with pytest.raises(CommandError):
        call_command(
            "evaluate_extraction_quality",
            assert_benchmarks_pass=True,
            benchmark_source=[source_missing, source_failing.location],
        )


@pytest.mark.django_db
def test_evaluate_extraction_quality_assert_benchmarks_requires_sources():
    with pytest.raises(CommandError):
        call_command(
            "evaluate_extraction_quality",
            assert_benchmarks_pass=True,
        )
