# Generated by Django 4.2.8 on 2024-02-07 18:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("templates", "0020_squashed"),
    ]

    operations = [
        migrations.AlterField(
            model_name="templatetranslation",
            name="components",
            field=models.JSONField(default=dict),
        ),
    ]