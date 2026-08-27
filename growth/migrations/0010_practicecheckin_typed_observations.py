from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("growth", "0009_personalosrevision")]

    operations = [
        migrations.AlterField(
            model_name="practiceprotocol",
            name="stable_id",
            field=models.CharField(max_length=120, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="evidenceevent",
            name="protocol_stable_id",
            field=models.CharField(max_length=120),
        ),
        migrations.AddField(
            model_name="practicecheckin",
            name="typed_observations",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
