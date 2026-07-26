from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0003_exercisesource_exercisecandidate"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExerciseExtractionRun",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("completed_with_errors", "Completed with errors"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=32,
                    ),
                ),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="extraction_runs",
                        to="workouts.exercisesource",
                    ),
                ),
            ],
            options={"ordering": ["-started_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ExerciseExtractionPage",
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
                ("page_number", models.PositiveIntegerField()),
                (
                    "extraction_method",
                    models.CharField(
                        choices=[
                            ("text_file", "Text file"),
                            ("pypdf", "PyPDF"),
                            ("unsupported", "Unsupported"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("extracted", "Extracted"),
                            ("partial", "Partial"),
                            ("failed", "Failed"),
                        ],
                        max_length=32,
                    ),
                ),
                ("raw_text", models.TextField(blank=True)),
                ("cleaned_text", models.TextField(blank=True)),
                ("char_count", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="pages",
                        to="workouts.exerciseextractionrun",
                    ),
                ),
            ],
            options={
                "ordering": ["page_number", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("run", "page_number"),
                        name="unique_page_number_per_extraction_run",
                    )
                ],
            },
        ),
    ]
