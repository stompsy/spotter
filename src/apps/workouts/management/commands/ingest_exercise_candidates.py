from __future__ import annotations

import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.workouts.models import (
    CurationStatus,
    ExerciseCandidate,
    ExerciseExtractionPage,
    ExerciseExtractionRun,
    ExerciseSource,
    ExerciseSourceType,
    ExtractionMethod,
    ExtractionPageStatus,
    ExtractionRunStatus,
)

LUNGE_PATTERNS = [
    re.compile(r"\bForward Lunges?\b", re.IGNORECASE),
    re.compile(r"\bRight Side Lunges?\b", re.IGNORECASE),
    re.compile(r"\bLeft Side Lunges?\b", re.IGNORECASE),
    re.compile(r"\bReverse Lunges?\b", re.IGNORECASE),
    re.compile(r"\bSwitch Lunges?\b", re.IGNORECASE),
]


def normalize_exercise_name(raw_name: str) -> str:
    cleaned = raw_name.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace("lunges", "lunge")

    if cleaned in {"right side lunge", "left side lunge"}:
        return "side lunge"

    return cleaned


def extract_candidates(raw_text: str) -> list[str]:
    candidates: list[str] = []

    for pattern in LUNGE_PATTERNS:
        for match in pattern.finditer(raw_text):
            candidates.append(match.group(0))

    if "master-the-plank" in raw_text.lower() or "master the plank" in raw_text.lower():
        candidates.append("Plank")

    return candidates


def clean_extracted_text(raw_text: str) -> str:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def extract_text_pages(source_file: Path) -> tuple[list[str], str, str | None]:
    suffix = source_file.suffix.lower()

    if suffix == ".txt":
        return [source_file.read_text(encoding="utf-8")], ExtractionMethod.TEXT_FILE, None

    if suffix == ".pdf":
        try:
            import pypdf
        except ModuleNotFoundError:
            return [], ExtractionMethod.PYPDF, "pypdf is not installed"

        pages: list[str] = []
        reader = pypdf.PdfReader(str(source_file))
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return pages, ExtractionMethod.PYPDF, None

    return [], ExtractionMethod.UNSUPPORTED, f"Unsupported source type: {suffix or 'none'}"


class Command(BaseCommand):
    help = "Ingest draft exercise candidates from a text source file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-file",
            default="docs/Lunges.txt",
            help="Path to the source text file",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print candidate output without writing to the database",
        )

    def handle(self, *args, **options):
        source_file = Path(options["source_file"])
        if not source_file.exists():
            raise CommandError(f"Source file not found: {source_file}")

        pages, extraction_method, extraction_error = extract_text_pages(source_file)

        normalized_map: dict[str, str] = {}
        for raw_text in pages:
            cleaned_text = clean_extracted_text(raw_text)
            extracted = extract_candidates(cleaned_text)
            for raw_name in extracted:
                normalized = normalize_exercise_name(raw_name)
                normalized_map.setdefault(normalized, raw_name)

        if options["dry_run"]:
            self.stdout.write(f"Found {len(normalized_map)} unique candidates")
            if extraction_error:
                self.stdout.write(self.style.WARNING(f"Extraction warning: {extraction_error}"))
            for normalized_name, raw_name in sorted(normalized_map.items()):
                self.stdout.write(f"- {normalized_name} (raw: {raw_name})")
            return

        source, _ = ExerciseSource.objects.get_or_create(
            location=str(source_file),
            defaults={
                "name": source_file.name,
                "source_type": ExerciseSourceType.DOCUMENT,
                "notes": "Imported by ingest_exercise_candidates command",
            },
        )

        extraction_run = ExerciseExtractionRun.objects.create(
            source=source,
            status=ExtractionRunStatus.RUNNING,
            summary={
                "method": extraction_method,
                "source_file": str(source_file),
            },
        )

        if extraction_error:
            extraction_run.status = ExtractionRunStatus.FAILED
            extraction_run.finished_at = timezone.now()
            extraction_run.summary = {
                **extraction_run.summary,
                "error": extraction_error,
            }
            extraction_run.save(update_fields=["status", "finished_at", "summary"])
            self.stdout.write(self.style.WARNING(f"Extraction warning: {extraction_error}"))

        created = 0
        for normalized_name, raw_name in normalized_map.items():
            confidence = 0.950 if "lunge" in normalized_name else 0.700
            _, candidate_created = ExerciseCandidate.objects.get_or_create(
                source=source,
                normalized_name=normalized_name,
                defaults={
                    "raw_name": raw_name,
                    "status": CurationStatus.DRAFT,
                    "confidence": confidence,
                },
            )
            if candidate_created:
                created += 1

        page_errors = 0
        pages_with_text = 0
        for index, raw_text in enumerate(pages, start=1):
            cleaned_text = clean_extracted_text(raw_text)
            char_count = len(cleaned_text)
            if char_count == 0:
                status = ExtractionPageStatus.PARTIAL
                page_errors += 1
            else:
                status = ExtractionPageStatus.EXTRACTED
                pages_with_text += 1

            ExerciseExtractionPage.objects.create(
                run=extraction_run,
                page_number=index,
                extraction_method=extraction_method,
                status=status,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                char_count=char_count,
            )

        if extraction_run.status != ExtractionRunStatus.FAILED:
            extraction_run.status = (
                ExtractionRunStatus.COMPLETED
                if page_errors == 0
                else ExtractionRunStatus.COMPLETED_WITH_ERRORS
            )
            extraction_run.finished_at = timezone.now()
            extraction_run.summary = {
                **extraction_run.summary,
                "pages_total": len(pages),
                "pages_with_text": pages_with_text,
                "page_errors": page_errors,
                "candidates_found": len(normalized_map),
                "candidates_created": created,
            }
            extraction_run.save(update_fields=["status", "finished_at", "summary"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingested {created} new draft candidates from {source_file}"
            )
        )
