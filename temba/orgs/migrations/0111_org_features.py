# Generated by Django 4.0.7 on 2022-11-22 15:30

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orgs", "0110_delete_orgactivity"),
    ]

    operations = [
        migrations.AddField(
            model_name="org",
            name="features",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(max_length=32), default=list, size=None
            ),
        ),
    ]
