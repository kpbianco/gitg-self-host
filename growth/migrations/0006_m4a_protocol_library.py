from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("growth", "0005_m3b_score_state")]

    operations = [
        migrations.AddField(
            model_name="practiceprotocol",
            name="completion_rules",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="practiceprotocol",
            name="setup_copy",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="practiceprotocol",
            name="check_in_fields",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="practiceprotocol",
            name="score_active",
            field=models.BooleanField(default=False),
        ),
    ]
