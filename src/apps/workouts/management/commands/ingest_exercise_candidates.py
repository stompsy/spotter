from __future__ import annotations

import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.workouts.models import (
    CurationStatus,
    ExerciseCandidate,
    ExerciseSource,
    ExerciseSourceType,
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

        raw_text = source_file.read_text(encoding="utf-8")
        extracted = extract_candidates(raw_text)

        normalized_map: dict[str, str] = {}
        for raw_name in extracted:
            normalized = normalize_exercise_name(raw_name)
            normalized_map.setdefault(normalized, raw_name)

        if options["dry_run"]:
            self.stdout.write(f"Found {len(normalized_map)} unique candidates")
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

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingested {created} new draft candidates from {source_file}"
            )
        )
