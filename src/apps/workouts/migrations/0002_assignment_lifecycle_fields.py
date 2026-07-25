from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="workoutplanassignment",
            name="paused_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workoutplanassignment",
            name="ended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
