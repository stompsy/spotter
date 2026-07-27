from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workouts", "0016_workoutchallengedaycompletion"),
    ]

    operations = [
        migrations.AlterField(
            model_name="exerciseextractionpage",
            name="extraction_method",
            field=models.CharField(
                choices=[
                    ("text_file", "Text file"),
                    ("pypdf", "PyPDF"),
                    ("pdfplumber", "pdfplumber"),
                    ("ocr_tesseract", "OCR (pypdfium2 + pytesseract)"),
                    ("csv_dataset", "CSV dataset"),
                    ("json_dataset", "JSON dataset"),
                    ("media_file", "Media file"),
                    ("manual_entry", "Manual entry"),
                    ("unsupported", "Unsupported"),
                ],
                max_length=32,
            ),
        ),
    ]
