from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0017_alter_exerciseextractionpage_extraction_method"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanSignalCandidate",
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
                ("signal_type", models.CharField(max_length=64)),
                ("signal_value", models.CharField(max_length=200)),
                (
                    "confidence",
                    models.DecimalField(decimal_places=3, default=0.0, max_digits=4),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "page",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.CASCADE,
                        related_name="plan_signal_candidates",
                        to="workouts.exerciseextractionpage",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="plan_signal_candidates",
                        to="workouts.exerciseextractionrun",
                    ),
                ),
            ],
            options={"ordering": ["-confidence", "signal_type", "signal_value", "id"]},
        ),
        migrations.CreateModel(
            name="SourceReference",
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
                ("reference_url", models.URLField(blank=True)),
                ("title", models.CharField(blank=True, max_length=255)),
                ("license_name", models.CharField(blank=True, max_length=200)),
                ("attribution_text", models.CharField(blank=True, max_length=300)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="source_references",
                        to="workouts.exercisecandidate",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name="references",
                        to="workouts.exercisesource",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
