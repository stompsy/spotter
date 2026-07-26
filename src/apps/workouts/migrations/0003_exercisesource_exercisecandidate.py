from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0002_assignment_lifecycle_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExerciseSource",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("document", "Document"),
                            ("web", "Web reference"),
                            ("dataset", "Dataset"),
                        ],
                        default="document",
                        max_length=32,
                    ),
                ),
                ("location", models.CharField(max_length=500, unique=True)),
                ("license_name", models.CharField(blank=True, max_length=200)),
                ("is_approved", models.BooleanField(default=False)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="ExerciseCandidate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("raw_name", models.CharField(max_length=200)),
                ("normalized_name", models.CharField(max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("needs_review", "Needs review"),
                            ("approved", "Approved"),
                            ("published", "Published"),
                            ("deprecated", "Deprecated"),
                        ],
                        default="draft",
                        max_length=32,
                    ),
                ),
                (
                    "confidence",
                    models.DecimalField(decimal_places=3, default=0.0, max_digits=4),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="candidates",
                        to="workouts.exercisesource",
                    ),
                ),
            ],
            options={
                "ordering": ["normalized_name", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("source", "normalized_name"),
                        name="unique_candidate_name_per_source",
                    )
                ],
            },
        ),
    ]
