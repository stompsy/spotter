from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.workouts.models import (
    Exercise,
    ExerciseBodyArea,
    ExerciseCategory,
    ExerciseDifficultyLevel,
    ExerciseDurationFit,
    ExerciseEquipmentRequirement,
    ExerciseMovementType,
    WorkoutChallengeDay,
    WorkoutPlan,
    WorkoutPlanItem,
    WorkoutPlanType,
)


class Command(BaseCommand):
    help = (
        "Seed curated workout bundles (warm-up, calisthenics, cooldown, "
        "30-day abs, 30-day lunge). Safe to run multiple times."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--created-by",
            required=True,
            help="Username to set as the creator for seeded plans.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        created_by_username = options["created_by"].strip()
        user_model = get_user_model()
        created_by = user_model.objects.filter(username=created_by_username).first()
        if created_by is None:
            raise CommandError(f"Unknown user for --created-by: {created_by_username}")

        exercises = self._seed_exercises()
        self._seed_warmup_bundle(created_by, exercises)
        self._seed_calisthenics_bundle(created_by, exercises)
        self._seed_cooldown_bundle(created_by, exercises)
        self._seed_abs_challenge_bundle(created_by, exercises)
        self._seed_lunge_challenge_bundle(created_by, exercises)

        self.stdout.write(self.style.SUCCESS("Curated bundles seeded."))

    def _seed_exercises(self) -> dict[str, Exercise]:
        specs = [
            {
                "key": "worlds_greatest_stretch",
                "name": "World's Greatest Stretch",
                "slug": "worlds-greatest-stretch",
                "category": ExerciseCategory.MOVEMENT_PREPARATION,
                "movement_type": ExerciseMovementType.MOBILITY,
                "primary_body_area": ExerciseBodyArea.HIPS,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.SHORT,
            },
            {
                "key": "inchworm_walkout",
                "name": "Inchworm Walkout",
                "slug": "inchworm-walkout",
                "category": ExerciseCategory.MOVEMENT_PREPARATION,
                "movement_type": ExerciseMovementType.CORE,
                "primary_body_area": ExerciseBodyArea.FULL_BODY,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.SHORT,
            },
            {
                "key": "scapular_pushup",
                "name": "Scapular Push-Up",
                "slug": "scapular-push-up",
                "category": ExerciseCategory.MOVEMENT_PREPARATION,
                "movement_type": ExerciseMovementType.PUSH,
                "primary_body_area": ExerciseBodyArea.SHOULDERS,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.SHORT,
            },
            {
                "key": "pushup",
                "name": "Push-Up",
                "slug": "push-up",
                "category": ExerciseCategory.CALISTHENICS,
                "movement_type": ExerciseMovementType.PUSH,
                "primary_body_area": ExerciseBodyArea.CHEST,
                "difficulty_level": ExerciseDifficultyLevel.INTERMEDIATE,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.MEDIUM,
            },
            {
                "key": "bodyweight_squat",
                "name": "Bodyweight Squat",
                "slug": "bodyweight-squat",
                "category": ExerciseCategory.CALISTHENICS,
                "movement_type": ExerciseMovementType.SQUAT,
                "primary_body_area": ExerciseBodyArea.LEGS,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.MEDIUM,
            },
            {
                "key": "hollow_hold",
                "name": "Hollow Hold",
                "slug": "hollow-hold",
                "category": ExerciseCategory.CORE_STABILITY,
                "movement_type": ExerciseMovementType.CORE,
                "primary_body_area": ExerciseBodyArea.CORE,
                "difficulty_level": ExerciseDifficultyLevel.INTERMEDIATE,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.MEDIUM,
            },
            {
                "key": "child_pose_breathing",
                "name": "Child Pose Breathing",
                "slug": "child-pose-breathing",
                "category": ExerciseCategory.POST_WORKOUT_REGENERATION,
                "movement_type": ExerciseMovementType.MOBILITY,
                "primary_body_area": ExerciseBodyArea.BACK,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.SHORT,
            },
            {
                "key": "supine_hamstring_stretch",
                "name": "Supine Hamstring Stretch",
                "slug": "supine-hamstring-stretch",
                "category": ExerciseCategory.POST_WORKOUT_REGENERATION,
                "movement_type": ExerciseMovementType.MOBILITY,
                "primary_body_area": ExerciseBodyArea.LEGS,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.SHORT,
            },
            {
                "key": "dead_bug",
                "name": "Dead Bug",
                "slug": "dead-bug",
                "category": ExerciseCategory.CORE_STABILITY,
                "movement_type": ExerciseMovementType.CORE,
                "primary_body_area": ExerciseBodyArea.CORE,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.SHORT,
            },
            {
                "key": "plank",
                "name": "Plank",
                "slug": "plank",
                "category": ExerciseCategory.CORE_STABILITY,
                "movement_type": ExerciseMovementType.CORE,
                "primary_body_area": ExerciseBodyArea.CORE,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.SHORT,
            },
            {
                "key": "forward_lunge",
                "name": "Forward Lunge",
                "slug": "forward-lunge",
                "category": ExerciseCategory.CALISTHENICS,
                "movement_type": ExerciseMovementType.LUNGE,
                "primary_body_area": ExerciseBodyArea.LEGS,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.MEDIUM,
            },
            {
                "key": "reverse_lunge",
                "name": "Reverse Lunge",
                "slug": "reverse-lunge",
                "category": ExerciseCategory.CALISTHENICS,
                "movement_type": ExerciseMovementType.LUNGE,
                "primary_body_area": ExerciseBodyArea.LEGS,
                "difficulty_level": ExerciseDifficultyLevel.BEGINNER,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.MEDIUM,
            },
            {
                "key": "lateral_lunge",
                "name": "Lateral Lunge",
                "slug": "lateral-lunge",
                "category": ExerciseCategory.CALISTHENICS,
                "movement_type": ExerciseMovementType.LUNGE,
                "primary_body_area": ExerciseBodyArea.LEGS,
                "difficulty_level": ExerciseDifficultyLevel.INTERMEDIATE,
                "equipment_requirement": ExerciseEquipmentRequirement.NONE,
                "duration_fit": ExerciseDurationFit.MEDIUM,
            },
        ]

        exercises: dict[str, Exercise] = {}
        for spec in specs:
            exercise, _ = Exercise.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "category": spec["category"],
                    "movement_type": spec["movement_type"],
                    "primary_body_area": spec["primary_body_area"],
                    "difficulty_level": spec["difficulty_level"],
                    "equipment_requirement": spec["equipment_requirement"],
                    "duration_fit": spec["duration_fit"],
                    "is_active": True,
                },
            )
            exercises[spec["key"]] = exercise
        return exercises

    def _seed_warmup_bundle(self, created_by, exercises: dict[str, Exercise]) -> None:
        plan, _ = WorkoutPlan.objects.update_or_create(
            slug="bundle-warm-up-foundations",
            defaults={
                "name": "Warm-Up Foundations",
                "description": (
                    "Short prep flow for joints, core activation, "
                    "and movement quality."
                ),
                "created_by": created_by,
                "plan_type": WorkoutPlanType.SINGLE_SESSION,
                "is_template": True,
                "is_published": True,
            },
        )
        self._replace_plan_items(
            plan,
            [
                {
                    "exercise": exercises["worlds_greatest_stretch"],
                    "repetitions": "2 rounds each side",
                    "duration_minutes": 4,
                },
                {
                    "exercise": exercises["inchworm_walkout"],
                    "repetitions": "8 reps",
                    "duration_minutes": 3,
                },
                {
                    "exercise": exercises["scapular_pushup"],
                    "repetitions": "12 reps",
                    "duration_minutes": 3,
                },
            ],
        )

    def _seed_calisthenics_bundle(self, created_by, exercises: dict[str, Exercise]) -> None:
        plan, _ = WorkoutPlan.objects.update_or_create(
            slug="bundle-calisthenics-base",
            defaults={
                "name": "Calisthenics Base Builder",
                "description": (
                    "Foundational push, squat, and core work "
                    "for general strength."
                ),
                "created_by": created_by,
                "plan_type": WorkoutPlanType.SINGLE_SESSION,
                "is_template": True,
                "is_published": True,
            },
        )
        self._replace_plan_items(
            plan,
            [
                {
                    "exercise": exercises["pushup"],
                    "repetitions": "4x8",
                    "duration_minutes": 8,
                },
                {
                    "exercise": exercises["bodyweight_squat"],
                    "repetitions": "4x12",
                    "duration_minutes": 8,
                },
                {
                    "exercise": exercises["hollow_hold"],
                    "repetitions": "4x30s",
                    "duration_minutes": 6,
                },
            ],
        )

    def _seed_cooldown_bundle(self, created_by, exercises: dict[str, Exercise]) -> None:
        plan, _ = WorkoutPlan.objects.update_or_create(
            slug="bundle-cooldown-reset",
            defaults={
                "name": "Cooldown Reset",
                "description": (
                    "Breathing and mobility sequence to "
                    "down-regulate after training."
                ),
                "created_by": created_by,
                "plan_type": WorkoutPlanType.SINGLE_SESSION,
                "is_template": True,
                "is_published": True,
            },
        )
        self._replace_plan_items(
            plan,
            [
                {
                    "exercise": exercises["child_pose_breathing"],
                    "repetitions": "2 rounds",
                    "duration_minutes": 4,
                },
                {
                    "exercise": exercises["supine_hamstring_stretch"],
                    "repetitions": "90s each side",
                    "duration_minutes": 4,
                },
                {
                    "exercise": exercises["worlds_greatest_stretch"],
                    "repetitions": "1 round each side",
                    "duration_minutes": 3,
                },
            ],
        )

    def _seed_abs_challenge_bundle(self, created_by, exercises: dict[str, Exercise]) -> None:
        plan, _ = WorkoutPlan.objects.update_or_create(
            slug="bundle-30-day-abs",
            defaults={
                "name": "30-Day Abs Challenge Seed",
                "description": (
                    "Progressive core challenge seed with "
                    "checkpoint cadence every 5 days."
                ),
                "created_by": created_by,
                "plan_type": WorkoutPlanType.CHALLENGE,
                "challenge_duration_days": 30,
                "challenge_focus_area": "Core",
                "is_template": True,
                "is_published": True,
            },
        )
        self._replace_challenge_days_and_items(
            plan=plan,
            day_count=30,
            focus_area="Core",
            exercise_cycle=[
                exercises["plank"],
                exercises["dead_bug"],
                exercises["hollow_hold"],
            ],
            target_minutes_fn=lambda day: 6 + ((day - 1) // 5) * 2,
            repetitions_fn=lambda day: f"{2 + ((day - 1) // 10)} rounds",
        )

    def _seed_lunge_challenge_bundle(self, created_by, exercises: dict[str, Exercise]) -> None:
        plan, _ = WorkoutPlan.objects.update_or_create(
            slug="bundle-30-day-lunge",
            defaults={
                "name": "30-Day Lunge Challenge Seed",
                "description": (
                    "Progressive lunge-volume challenge seed with "
                    "checkpoint cadence every 5 days."
                ),
                "created_by": created_by,
                "plan_type": WorkoutPlanType.CHALLENGE,
                "challenge_duration_days": 30,
                "challenge_focus_area": "Legs",
                "is_template": True,
                "is_published": True,
            },
        )
        self._replace_challenge_days_and_items(
            plan=plan,
            day_count=30,
            focus_area="Legs",
            exercise_cycle=[
                exercises["forward_lunge"],
                exercises["reverse_lunge"],
                exercises["lateral_lunge"],
            ],
            target_minutes_fn=lambda day: 8 + ((day - 1) // 6) * 2,
            repetitions_fn=lambda day: f"{8 + day} reps each side",
        )

    def _replace_plan_items(self, plan: WorkoutPlan, item_specs: list[dict]) -> None:
        plan.items.all().delete()
        for order, spec in enumerate(item_specs, start=1):
            WorkoutPlanItem.objects.create(
                plan=plan,
                order=order,
                exercise=spec["exercise"],
                repetitions=spec.get("repetitions", ""),
                duration_minutes=spec.get("duration_minutes"),
                notes=spec.get("notes", ""),
            )

    def _replace_challenge_days_and_items(
        self,
        plan: WorkoutPlan,
        day_count: int,
        focus_area: str,
        exercise_cycle: list[Exercise],
        target_minutes_fn,
        repetitions_fn,
    ) -> None:
        plan.items.all().delete()
        plan.challenge_days.all().delete()

        for day_number in range(1, day_count + 1):
            target_minutes = int(target_minutes_fn(day_number))
            checkpoint_note = "Checkpoint" if day_number % 5 == 0 else ""
            challenge_day = WorkoutChallengeDay.objects.create(
                plan=plan,
                day_number=day_number,
                title=f"Day {day_number}",
                focus_area=focus_area,
                target_duration_minutes=target_minutes,
                notes=checkpoint_note,
            )

            exercise = exercise_cycle[(day_number - 1) % len(exercise_cycle)]
            WorkoutPlanItem.objects.create(
                plan=plan,
                challenge_day=challenge_day,
                order=day_number,
                exercise=exercise,
                repetitions=repetitions_fn(day_number),
                duration_minutes=target_minutes,
            )