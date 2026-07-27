from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
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
    PlanSignalCandidate,
    SourceReference,
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

PDF_LOW_YIELD_THRESHOLD = 80
LOW_CONFIDENCE_THRESHOLD = 0.65

PLAN_SIGNAL_PATTERNS = {
    "challenge_day": re.compile(r"\bday\s+(\d{1,3})\b", re.IGNORECASE),
    "week_marker": re.compile(r"\bweek\s+(\d{1,2})\b", re.IGNORECASE),
    "phase_marker": re.compile(r"\bphase\s+([a-z0-9-]+)\b", re.IGNORECASE),
    "rep_set_directive": re.compile(
        r"\b(\d+\s*x\s*\d+|\d+\s*(?:reps?|sets?|seconds?|minutes?))\b",
        re.IGNORECASE,
    ),
}


def normalize_exercise_name(raw_name: str) -> str:
    cleaned = raw_name.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.split(":", maxsplit=1)[0].strip()
    cleaned = cleaned.replace("lunges", "lunge")

    if cleaned in {"right side lunge", "left side lunge"}:
        return "side lunge"

    return cleaned[:200].strip()


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


def _pdfplumber_page_text(source_file: Path, page_index: int) -> tuple[str, str | None]:
    try:
        import pdfplumber
    except ModuleNotFoundError:
        return "", "pdfplumber is not installed"

    with pdfplumber.open(str(source_file)) as document:
        if page_index >= len(document.pages):
            return "", f"pdfplumber page out of range: {page_index}"
        return document.pages[page_index].extract_text() or "", None


def _ocr_page_text(source_file: Path, page_index: int) -> tuple[str, str | None]:
    try:
        import pypdfium2 as pdfium
    except ModuleNotFoundError:
        return "", "pypdfium2 is not installed"

    try:
        import pytesseract
    except ModuleNotFoundError:
        return "", "pytesseract is not installed"

    pdf = pdfium.PdfDocument(str(source_file))
    if page_index >= len(pdf):
        return "", f"ocr page out of range: {page_index}"

    page = pdf[page_index]
    bitmap = page.render(scale=2.0)
    pil_image = bitmap.to_pil()
    return pytesseract.image_to_string(pil_image) or "", None


def _build_extraction_page_record(
    page_number: int,
    raw_text: str,
    extraction_method: str,
    warnings: list[dict[str, str]] | None = None,
    attempted_methods: list[str] | None = None,
) -> dict:
    return {
        "page_number": page_number,
        "raw_text": raw_text,
        "extraction_method": extraction_method,
        "metadata": {
            "warnings": warnings or [],
            "attempted_methods": attempted_methods or [extraction_method],
        },
    }


def extract_document_pages(source_file: Path) -> tuple[list[dict], str, str | None]:
    suffix = source_file.suffix.lower()

    if suffix == ".txt":
        return [
            _build_extraction_page_record(
                page_number=1,
                raw_text=source_file.read_text(encoding="utf-8"),
                extraction_method=ExtractionMethod.TEXT_FILE,
            )
        ], ExtractionMethod.TEXT_FILE, None

    if suffix == ".pdf":
        try:
            import pypdf
        except ModuleNotFoundError:
            return [], ExtractionMethod.PYPDF, "pypdf is not installed"

        page_records: list[dict] = []
        reader = pypdf.PdfReader(str(source_file))
        for page_index, page in enumerate(reader.pages):
            warnings: list[dict[str, str]] = []
            attempted_methods = [ExtractionMethod.PYPDF]
            selected_text = page.extract_text() or ""
            selected_method = ExtractionMethod.PYPDF

            if len(clean_extracted_text(selected_text)) < PDF_LOW_YIELD_THRESHOLD:
                attempted_methods.append(ExtractionMethod.PDFPLUMBER)
                fallback_text, fallback_error = _pdfplumber_page_text(source_file, page_index)
                if fallback_error:
                    warnings.append(
                        {
                            "stage": ExtractionMethod.PDFPLUMBER,
                            "message": fallback_error,
                        }
                    )
                elif len(clean_extracted_text(fallback_text)) > len(clean_extracted_text(selected_text)):
                    selected_text = fallback_text
                    selected_method = ExtractionMethod.PDFPLUMBER

            if len(clean_extracted_text(selected_text)) < PDF_LOW_YIELD_THRESHOLD:
                attempted_methods.append(ExtractionMethod.OCR_TESSERACT)
                ocr_text, ocr_error = _ocr_page_text(source_file, page_index)
                if ocr_error:
                    warnings.append(
                        {
                            "stage": ExtractionMethod.OCR_TESSERACT,
                            "message": ocr_error,
                        }
                    )
                elif len(clean_extracted_text(ocr_text)) > len(clean_extracted_text(selected_text)):
                    selected_text = ocr_text
                    selected_method = ExtractionMethod.OCR_TESSERACT

            page_records.append(
                _build_extraction_page_record(
                    page_number=page_index + 1,
                    raw_text=selected_text,
                    extraction_method=selected_method,
                    warnings=warnings,
                    attempted_methods=attempted_methods,
                )
            )

        return page_records, "pdf_parser_routing", None

    return [], ExtractionMethod.UNSUPPORTED, f"Unsupported source type: {suffix or 'none'}"


def extract_text_pages(source_file: Path) -> tuple[list[str], str, str | None]:
    page_records, extraction_method, extraction_error = extract_document_pages(source_file)
    return [page_record["raw_text"] for page_record in page_records], extraction_method, extraction_error


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
        return ["\n".join(names)], ExtractionMethod.CSV_DATASET, None

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

        return ["\n".join(names)], ExtractionMethod.JSON_DATASET, None

    return [], ExtractionMethod.UNSUPPORTED, f"Unsupported dataset type: {suffix or 'none'}"


def extract_media_pages(source_file: Path) -> tuple[list[str], str, str | None]:
    suffix = source_file.suffix.lower()
    supported_media_suffixes = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov"}
    if suffix not in supported_media_suffixes:
        return [], ExtractionMethod.UNSUPPORTED, f"Unsupported media type: {suffix or 'none'}"

    candidate_name = source_file.stem.replace("_", " ").replace("-", " ").strip()
    return [candidate_name], ExtractionMethod.MEDIA_FILE, None


def extract_manual_pages(candidate_names: list[str]) -> tuple[list[str], str, str | None]:
    names = [name.strip() for name in candidate_names if name.strip()]
    return ["\n".join(names)], ExtractionMethod.MANUAL_ENTRY, None


def _token_completeness_score(text: str, tokens: set[str]) -> float:
    lowered = text.lower()
    token_hits = sum(1 for token in tokens if token in lowered)
    if token_hits <= 0:
        return 0.0
    return min(token_hits / 4.0, 1.0)


def _score_candidate_confidence(
    normalized_name: str,
    raw_name: str,
    adapter: str,
    name_frequency: int,
) -> float:
    score = 0.50

    if "lunge" in normalized_name or "plank" in normalized_name:
        score += 0.25
    if 1 <= len(raw_name.split()) <= 4:
        score += 0.10
    if adapter in {"dataset", "manual"}:
        score += 0.10
    if name_frequency > 1:
        score += 0.05

    return max(0.20, min(score, 0.99))


def extract_plan_signals(cleaned_text: str) -> list[dict[str, str | float]]:
    signals: list[dict[str, str | float]] = []
    seen: set[tuple[str, str]] = set()
    for signal_type, pattern in PLAN_SIGNAL_PATTERNS.items():
        for match in pattern.finditer(cleaned_text):
            signal_value = re.sub(r"\s+", " ", match.group(0)).strip()
            dedupe_key = (signal_type, signal_value.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            signals.append(
                {
                    "signal_type": signal_type,
                    "signal_value": signal_value,
                    "confidence": 0.80,
                    "metadata": {
                        "match": match.group(0),
                    },
                }
            )
    return signals


def _source_reference_url(source_location: str) -> str:
    if source_location.lower().startswith(("http://", "https://")):
        return source_location
    return ""


def _sync_ingestion_source_reference(
    *,
    candidate: ExerciseCandidate,
    source: ExerciseSource,
    source_location: str,
    adapter: str,
) -> None:
    reference_url = _source_reference_url(source_location)
    SourceReference.objects.update_or_create(
        candidate=candidate,
        source=source,
        reference_url=reference_url,
        defaults={
            "title": source.name,
            "license_name": source.license_name,
            "attribution_text": "",
            "metadata": {
                "captured_by": "ingestion_command",
                "adapter": adapter,
            },
        },
    )


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
        selected_adapter = adapter

        if adapter == "manual":
            if not candidate_names:
                raise CommandError("Manual adapter requires at least one --candidate-name")
            pages, extraction_method, extraction_error = extract_manual_pages(candidate_names)
            extraction_page_records = [
                _build_extraction_page_record(
                    page_number=1,
                    raw_text=pages[0] if pages else "",
                    extraction_method=ExtractionMethod.MANUAL_ENTRY,
                )
            ]
            selected_adapter = "manual"
            source_location = "manual://cli"
            source_name = "manual_entries"
            source_type = ExerciseSourceType.DOCUMENT
        else:
            if not source_file.exists():
                raise CommandError(f"Source file not found: {source_file}")

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
                extraction_page_records, extraction_method, extraction_error = extract_document_pages(
                    source_file
                )
                pages = [record["raw_text"] for record in extraction_page_records]
                source_type = ExerciseSourceType.DOCUMENT
            elif selected_adapter == "dataset":
                pages, extraction_method, extraction_error = extract_dataset_pages(source_file)
                extraction_page_records = [
                    _build_extraction_page_record(
                        page_number=1,
                        raw_text=pages[0] if pages else "",
                        extraction_method=extraction_method,
                    )
                ]
                source_type = ExerciseSourceType.DATASET
            elif selected_adapter == "media":
                pages, extraction_method, extraction_error = extract_media_pages(source_file)
                extraction_page_records = [
                    _build_extraction_page_record(
                        page_number=1,
                        raw_text=pages[0] if pages else "",
                        extraction_method=ExtractionMethod.MEDIA_FILE,
                    )
                ]
                source_type = ExerciseSourceType.WEB
            else:
                raise CommandError(f"Unsupported adapter: {selected_adapter}")

            source_location = str(source_file)
            source_name = source_file.name

        normalized_map: dict[str, str] = {}
        normalized_frequency: Counter[str] = Counter()
        combined_cleaned_text = ""
        for raw_text in pages:
            cleaned_text = clean_extracted_text(raw_text)
            combined_cleaned_text = f"{combined_cleaned_text}\n{cleaned_text}".strip()
            extracted = extract_candidates(cleaned_text)
            for raw_name in extracted:
                raw_name_for_storage = raw_name.strip()[:200].strip()
                if not raw_name_for_storage:
                    continue
                normalized = normalize_exercise_name(raw_name_for_storage)
                if not normalized:
                    continue
                normalized_map.setdefault(normalized, raw_name_for_storage)
                normalized_frequency[normalized] += 1

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
                "resolved_adapter": selected_adapter,
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
        low_confidence_candidates: list[str] = []
        source_reference_count = 0
        existing_duplicate_counts = {
            row["normalized_name"]: int(row["total"])
            for row in ExerciseCandidate.objects.filter(
                normalized_name__in=normalized_map.keys(),
            )
            .values("normalized_name")
            .annotate(total=Count("id"))
        }
        for normalized_name, raw_name in normalized_map.items():
            confidence = _score_candidate_confidence(
                normalized_name=normalized_name,
                raw_name=raw_name,
                adapter=selected_adapter,
                name_frequency=normalized_frequency.get(normalized_name, 1),
            )
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
                "needs_low_confidence_review": confidence < LOW_CONFIDENCE_THRESHOLD,
            }

            metadata = dict(candidate.metadata) if isinstance(candidate.metadata, dict) else {}
            metadata["quality_checks"] = quality_checks
            metadata["extraction"] = {
                "adapter": selected_adapter,
                "source_file": source_location,
            }
            candidate.metadata = metadata
            candidate.confidence = confidence
            if confidence < LOW_CONFIDENCE_THRESHOLD and candidate.status == CurationStatus.DRAFT:
                candidate.status = CurationStatus.NEEDS_REVIEW
                candidate.save(
                    update_fields=["status", "confidence", "metadata", "updated_at"]
                )
            else:
                candidate.save(update_fields=["confidence", "metadata", "updated_at"])

            if confidence < LOW_CONFIDENCE_THRESHOLD:
                low_confidence_candidates.append(normalized_name)

            _sync_ingestion_source_reference(
                candidate=candidate,
                source=source,
                source_location=source_location,
                adapter=selected_adapter,
            )
            source_reference_count += 1

            if candidate_created:
                created += 1

        page_errors = 0
        pages_with_text = 0
        page_methods: Counter[str] = Counter()
        plan_signal_count = 0
        parser_warning_count = 0
        parser_warning_stages: Counter[str] = Counter()
        for page_record in extraction_page_records:
            index = page_record["page_number"]
            raw_text = page_record["raw_text"]
            cleaned_text = clean_extracted_text(raw_text)
            char_count = len(cleaned_text)
            page_method = page_record.get("extraction_method", extraction_method)
            page_methods[page_method] += 1
            warning_entries = page_record.get("metadata", {}).get("warnings", [])
            parser_warning_count += len(warning_entries)
            for warning_entry in warning_entries:
                warning_stage = warning_entry.get("stage", "unknown")
                parser_warning_stages[warning_stage] += 1

            if char_count == 0 and warning_entries:
                status = ExtractionPageStatus.FAILED
                page_errors += 1
            elif char_count == 0:
                status = ExtractionPageStatus.PARTIAL
                page_errors += 1
            else:
                status = ExtractionPageStatus.EXTRACTED
                pages_with_text += 1

            extraction_page = ExerciseExtractionPage.objects.create(
                run=extraction_run,
                page_number=index,
                extraction_method=page_method,
                status=status,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                char_count=char_count,
                metadata=page_record.get("metadata", {}),
            )

            for signal in extract_plan_signals(cleaned_text):
                PlanSignalCandidate.objects.create(
                    run=extraction_run,
                    page=extraction_page,
                    signal_type=signal["signal_type"],
                    signal_value=signal["signal_value"],
                    confidence=signal["confidence"],
                    metadata=signal["metadata"],
                )
                plan_signal_count += 1

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
                "page_methods": dict(page_methods),
                "plan_signal_count": plan_signal_count,
                "parser_warning_count": parser_warning_count,
                "parser_warning_stages": dict(parser_warning_stages),
                "candidates_found": len(normalized_map),
                "candidates_created": created,
                "source_reference_count": source_reference_count,
                "low_confidence_candidate_count": len(low_confidence_candidates),
                "low_confidence_candidates": sorted(low_confidence_candidates),
            }
            extraction_run.save(update_fields=["status", "finished_at", "summary"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingested {created} new draft candidates from {source_location}"
            )
        )
