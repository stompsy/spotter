from __future__ import annotations

from typing import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.workouts.models import CurationStatus, ExerciseCandidate, ExerciseExtractionRun


class Command(BaseCommand):
    help = (
        "Evaluate extraction verification targets for a run: non-empty page ratio "
        "and high-confidence precision."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-by-source",
            action="store_true",
            help="Print a verification pass/fail leaderboard using latest run per source.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Maximum number of sources to show in report-by-source mode.",
        )
        parser.add_argument(
            "--benchmark-source",
            action="append",
            default=[],
            help=(
                "Source location expected to satisfy verification targets. "
                "Repeat for multiple benchmark sources."
            ),
        )
        parser.add_argument(
            "--assert-benchmarks-pass",
            action="store_true",
            help=(
                "Require all --benchmark-source latest runs to have PASS verification; "
                "raises CommandError if any are missing or failing."
            ),
        )
        parser.add_argument(
            "--run-id",
            type=int,
            help="Evaluate a specific extraction run id.",
        )
        parser.add_argument(
            "--source-location",
            help="Evaluate the latest extraction run for this source location.",
        )
        parser.add_argument(
            "--expected-candidate",
            action="append",
            default=[],
            help="Expected normalized candidate names (repeat flag for multiple values).",
        )
        parser.add_argument(
            "--min-non-empty-ratio",
            type=float,
            default=0.90,
            help="Minimum passing threshold for non-empty page ratio.",
        )
        parser.add_argument(
            "--min-high-confidence-precision",
            type=float,
            default=0.90,
            help="Minimum passing threshold for high-confidence precision.",
        )

    def handle(self, *args, **options):
        if options.get("assert_benchmarks_pass"):
            self._assert_benchmark_sources_pass(
                benchmark_sources=options.get("benchmark_source", [])
            )
            return

        if options.get("report_by_source"):
            self._report_by_source(limit=max(int(options["limit"]), 1))
            return

        extraction_run = self._resolve_run(
            run_id=options.get("run_id"),
            source_location=options.get("source_location"),
        )

        expected_candidates = self._normalize_expected_names(
            options.get("expected_candidate", [])
        )
        if not expected_candidates:
            expected_candidates = self._derive_expected_names_from_review_status(extraction_run)

        page_qs = extraction_run.pages.all()
        pages_total = page_qs.count()
        pages_with_text = page_qs.filter(char_count__gt=0).count()
        non_empty_ratio = (pages_with_text / pages_total) if pages_total else 0.0

        high_conf_qs = ExerciseCandidate.objects.filter(
            source=extraction_run.source,
            confidence__gte=0.85,
        )
        high_conf_names = {
            name.strip().lower()
            for name in high_conf_qs.values_list("normalized_name", flat=True)
        }

        high_conf_count = len(high_conf_names)
        expected_count = len(expected_candidates)
        true_positives = len(high_conf_names.intersection(expected_candidates))
        high_conf_precision = (true_positives / high_conf_count) if high_conf_count else 0.0

        min_non_empty_ratio = float(options["min_non_empty_ratio"])
        min_precision = float(options["min_high_confidence_precision"])

        non_empty_pass = non_empty_ratio >= min_non_empty_ratio
        precision_pass = high_conf_precision >= min_precision

        verification_summary = {
            "pages_total": pages_total,
            "pages_with_text": pages_with_text,
            "non_empty_page_ratio": round(non_empty_ratio, 4),
            "min_non_empty_page_ratio": min_non_empty_ratio,
            "non_empty_page_ratio_pass": non_empty_pass,
            "high_confidence_candidate_count": high_conf_count,
            "expected_candidate_count": expected_count,
            "high_confidence_true_positives": true_positives,
            "high_confidence_precision": round(high_conf_precision, 4),
            "min_high_confidence_precision": min_precision,
            "high_confidence_precision_pass": precision_pass,
            "evaluated_at": timezone.now().isoformat(),
        }

        extraction_run.summary = {
            **(extraction_run.summary or {}),
            "verification": verification_summary,
        }
        extraction_run.save(update_fields=["summary"])

        self.stdout.write(
            "Run %s source %s" % (extraction_run.id, extraction_run.source.location)
        )
        self.stdout.write(
            "Extraction quality %.3f (%s/%s) threshold %.3f => %s"
            % (
                non_empty_ratio,
                pages_with_text,
                pages_total,
                min_non_empty_ratio,
                "PASS" if non_empty_pass else "FAIL",
            )
        )
        self.stdout.write(
            "High-confidence precision %.3f (%s/%s) threshold %.3f => %s"
            % (
                high_conf_precision,
                true_positives,
                high_conf_count,
                min_precision,
                "PASS" if precision_pass else "FAIL",
            )
        )

        if non_empty_pass and precision_pass:
            self.stdout.write(self.style.SUCCESS("Verification targets satisfied."))
        else:
            self.stdout.write(self.style.WARNING("Verification targets not yet satisfied."))

    def _assert_benchmark_sources_pass(self, *, benchmark_sources: list[str]) -> None:
        normalized_sources = [source.strip() for source in benchmark_sources if source.strip()]
        if not normalized_sources:
            raise CommandError(
                "--assert-benchmarks-pass requires at least one --benchmark-source"
            )

        failed_sources: list[str] = []
        for source_location in normalized_sources:
            run = (
                ExerciseExtractionRun.objects.filter(source__location=source_location)
                .order_by("-started_at", "-id")
                .first()
            )
            if run is None:
                failed_sources.append(f"{source_location} (no runs)")
                continue

            verification = (run.summary or {}).get("verification", {})
            non_empty_pass = verification.get("non_empty_page_ratio_pass") is True
            precision_pass = verification.get("high_confidence_precision_pass") is True
            if not (non_empty_pass and precision_pass):
                failed_sources.append(f"{source_location} (run {run.id} not passing)")
                continue

            self.stdout.write(
                self.style.SUCCESS(
                    "BENCHMARK PASS source=%s run=%s" % (source_location, run.id)
                )
            )

        if failed_sources:
            failed_summary = ", ".join(failed_sources)
            raise CommandError(
                "Benchmark verification targets not satisfied: %s" % failed_summary
            )

        self.stdout.write(self.style.SUCCESS("All benchmark sources satisfy verification targets."))

    def _report_by_source(self, *, limit: int) -> None:
        runs = ExerciseExtractionRun.objects.select_related("source").order_by(
            "-started_at",
            "-id",
        )
        if not runs.exists():
            raise CommandError("No extraction runs available to report")

        latest_by_source: dict[int, ExerciseExtractionRun] = {}
        for run in runs:
            if run.source_id in latest_by_source:
                continue
            latest_by_source[run.source_id] = run

        selected_runs = list(latest_by_source.values())[:limit]
        self.stdout.write(
            "Source verification leaderboard (latest run per source, top %s)" % limit
        )
        for run in selected_runs:
            verification = (run.summary or {}).get("verification", {})
            non_empty_ratio = verification.get("non_empty_page_ratio")
            precision = verification.get("high_confidence_precision")
            non_empty_pass = verification.get("non_empty_page_ratio_pass")
            precision_pass = verification.get("high_confidence_precision_pass")

            if non_empty_pass is True and precision_pass is True:
                status = "PASS"
            elif non_empty_ratio is None and precision is None:
                status = "PENDING"
            else:
                status = "FAIL"

            non_empty_display = (
                f"{float(non_empty_ratio):.3f}" if non_empty_ratio is not None else "n/a"
            )
            precision_display = (
                f"{float(precision):.3f}" if precision is not None else "n/a"
            )

            self.stdout.write(
                "[%s] run=%s source=%s non_empty=%s precision=%s"
                % (
                    status,
                    run.id,
                    run.source.location,
                    non_empty_display,
                    precision_display,
                )
            )

    def _resolve_run(self, *, run_id: int | None, source_location: str | None) -> ExerciseExtractionRun:
        if run_id is not None:
            run = ExerciseExtractionRun.objects.filter(id=run_id).first()
            if run is None:
                raise CommandError(f"Extraction run not found: {run_id}")
            return run

        if source_location:
            run = (
                ExerciseExtractionRun.objects.filter(source__location=source_location)
                .order_by("-started_at", "-id")
                .first()
            )
            if run is None:
                raise CommandError(
                    f"No extraction run found for source location: {source_location}"
                )
            return run

        run = ExerciseExtractionRun.objects.order_by("-started_at", "-id").first()
        if run is None:
            raise CommandError("No extraction runs available to evaluate")
        return run

    def _normalize_expected_names(self, values: Iterable[str]) -> set[str]:
        return {
            value.strip().lower()
            for value in values
            if isinstance(value, str) and value.strip()
        }

    def _derive_expected_names_from_review_status(
        self,
        extraction_run: ExerciseExtractionRun,
    ) -> set[str]:
        return {
            value.strip().lower()
            for value in ExerciseCandidate.objects.filter(
                source=extraction_run.source,
                status__in=[CurationStatus.APPROVED, CurationStatus.PUBLISHED],
            ).values_list("normalized_name", flat=True)
            if value and value.strip()
        }
