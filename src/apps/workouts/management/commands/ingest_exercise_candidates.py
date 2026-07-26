from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from django.db.models import Count
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

INSTRUCTION_TOKENS = {
    "set",
    "sets",
    "rep",
    "reps",
    "minute",
    "minutes",
    "second",
    "seconds",
    "tempo",
    "hold",
}

SAFETY_TOKENS = {
    "warm up",
    "warm-up",
    "form",
    "control",
    "pain",
    "stop",
    "recover",
    "rest",
    "breath",
    "alignment",
}


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

    for line in raw_text.splitlines():
        cleaned = line.strip().lstrip("-*").strip()
        if not cleaned:
            continue
        if cleaned.lower().startswith("http://") or cleaned.lower().startswith("https://"):
            continue

        if any(char.isalpha() for char in cleaned):
            cleaned = re.sub(r"\s+", " ", cleaned)
            cleaned = re.sub(r"^[0-9]+\s+", "", cleaned)
            cleaned = re.sub(r"\([^)]*\)", "", cleaned).strip()
            if cleaned:
                candidates.append(cleaned)

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


def extract_dataset_pages(source_file: Path) -> tuple[list[str], str, str | None]:
    suffix = source_file.suffix.lower()

    if suffix == ".csv":
        rows = list(csv.reader(source_file.read_text(encoding="utf-8").splitlines()))
        if not rows:
            return [""], "csv_dataset", None

        header = [cell.strip().lower() for cell in rows[0]]
        start_index = 0
        name_index = 0
        if "name" in header:
            name_index = header.index("name")
            start_index = 1

        names = []
        for row in rows[start_index:]:
            if name_index >= len(row):
                continue
            raw_name = row[name_index].strip()
            if raw_name:
                names.append(raw_name)
        return ["\n".join(names)], "csv_dataset", None

    if suffix == ".json":
        data = json.loads(source_file.read_text(encoding="utf-8"))
        names: list[str] = []

        if isinstance(data, list):
            for item in data:
                if isinstance(item, str) and item.strip():
                    names.append(item.strip())
                elif isinstance(item, dict):
                    raw_name = str(item.get("name") or item.get("raw_name") or "").strip()
                    if raw_name:
                        names.append(raw_name)

        return ["\n".join(names)], "json_dataset", None

    return [], ExtractionMethod.UNSUPPORTED, f"Unsupported dataset type: {suffix or 'none'}"


def extract_media_pages(source_file: Path) -> tuple[list[str], str, str | None]:
    suffix = source_file.suffix.lower()
    supported_media_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov"}
    if suffix not in supported_media_suffixes:
        return [], ExtractionMethod.UNSUPPORTED, f"Unsupported media type: {suffix or 'none'}"

    candidate_name = source_file.stem.replace("_", " ").replace("-", " ").strip()
    return [candidate_name], "media_file", None


def extract_manual_pages(candidate_names: list[str]) -> tuple[list[str], str, str | None]:
    names = [name.strip() for name in candidate_names if name.strip()]
    return ["\n".join(names)], "manual_entry", None


def _token_completeness_score(text: str, tokens: set[str]) -> float:
    lowered = text.lower()
    token_hits = sum(1 for token in tokens if token in lowered)
    if token_hits <= 0:
        return 0.0
    return min(token_hits / 4.0, 1.0)


class Command(BaseCommand):
    help = "Ingest draft exercise candidates from a text source file"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-file",
            default="docs/Lunges.txt",
            help="Path to the source text file",
        )
        parser.add_argument(
            "--adapter",
            choices=["auto", "document", "dataset", "media", "manual"],
            default="auto",
            help="Select ingestion adapter. Default auto routes by file type.",
        )
        parser.add_argument(
            "--candidate-name",
            action="append",
            default=[],
            help="Manual adapter candidate name. Repeat for multiple values.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print candidate output without writing to the database",
        )

    def handle(self, *args, **options):
        adapter = options["adapter"]
        source_file = Path(options["source_file"])
        candidate_names = options["candidate_name"]

        if adapter == "manual":
            if not candidate_names:
                raise CommandError("Manual adapter requires at least one --candidate-name")
            pages, extraction_method, extraction_error = extract_manual_pages(candidate_names)
            source_location = "manual://cli"
            source_name = "manual_entries"
            source_type = ExerciseSourceType.DOCUMENT
        else:
            if not source_file.exists():
                raise CommandError(f"Source file not found: {source_file}")

            selected_adapter = adapter
            if selected_adapter == "auto":
                suffix = source_file.suffix.lower()
                if suffix in {".txt", ".pdf"}:
                    selected_adapter = "document"
                elif suffix in {".csv", ".json"}:
                    selected_adapter = "dataset"
                elif suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov"}:
                    selected_adapter = "media"
                else:
                    selected_adapter = "document"

            if selected_adapter == "document":
                pages, extraction_method, extraction_error = extract_text_pages(source_file)
                source_type = ExerciseSourceType.DOCUMENT
            elif selected_adapter == "dataset":
                pages, extraction_method, extraction_error = extract_dataset_pages(source_file)
                source_type = ExerciseSourceType.DATASET
            elif selected_adapter == "media":
                pages, extraction_method, extraction_error = extract_media_pages(source_file)
                source_type = ExerciseSourceType.WEB
            else:
                raise CommandError(f"Unsupported adapter: {selected_adapter}")

            source_location = str(source_file)
            source_name = source_file.name

        normalized_map: dict[str, str] = {}
        combined_cleaned_text = ""
        for raw_text in pages:
            cleaned_text = clean_extracted_text(raw_text)
            combined_cleaned_text = f"{combined_cleaned_text}\n{cleaned_text}".strip()
            extracted = extract_candidates(cleaned_text)
            for raw_name in extracted:
                normalized = normalize_exercise_name(raw_name)
                normalized_map.setdefault(normalized, raw_name)

        instruction_score = _token_completeness_score(combined_cleaned_text, INSTRUCTION_TOKENS)
        safety_score = _token_completeness_score(combined_cleaned_text, SAFETY_TOKENS)

        if options["dry_run"]:
            self.stdout.write(f"Found {len(normalized_map)} unique candidates")
            if extraction_error:
                self.stdout.write(self.style.WARNING(f"Extraction warning: {extraction_error}"))
            for normalized_name, raw_name in sorted(normalized_map.items()):
                self.stdout.write(f"- {normalized_name} (raw: {raw_name})")
            return

        source, _ = ExerciseSource.objects.get_or_create(
            location=source_location,
            defaults={
                "name": source_name,
                "source_type": source_type,
                "notes": "Imported by ingest_exercise_candidates command",
            },
        )

        extraction_run = ExerciseExtractionRun.objects.create(
            source=source,
            status=ExtractionRunStatus.RUNNING,
            summary={
                "method": extraction_method,
                "source_file": source_location,
                "adapter": adapter,
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
        existing_duplicate_counts = {
            row["normalized_name"]: int(row["total"])
            for row in ExerciseCandidate.objects.filter(
                normalized_name__in=normalized_map.keys(),
            )
            .values("normalized_name")
            .annotate(total=Count("id"))
        }
        for normalized_name, raw_name in normalized_map.items():
            confidence = 0.950 if "lunge" in normalized_name else 0.700
            candidate, candidate_created = ExerciseCandidate.objects.get_or_create(
                source=source,
                normalized_name=normalized_name,
                defaults={
                    "raw_name": raw_name,
                    "status": CurationStatus.DRAFT,
                    "confidence": confidence,
                },
            )

            duplicate_count = existing_duplicate_counts.get(normalized_name, 0)
            if candidate_created:
                duplicate_count += 1
            quality_checks = {
                "duplicate_candidates": duplicate_count > 1,
                "duplicate_count": duplicate_count,
                "instruction_completeness_score": instruction_score,
                "safety_completeness_score": safety_score,
            }

            metadata = dict(candidate.metadata) if isinstance(candidate.metadata, dict) else {}
            metadata["quality_checks"] = quality_checks
            candidate.metadata = metadata
            candidate.save(update_fields=["metadata", "updated_at"])

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
                f"Ingested {created} new draft candidates from {source_location}"
            )
        )
