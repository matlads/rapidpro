# Generated by Django 4.0.7 on 2022-09-16 16:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ivr", "0018_squashed"),
    ]

    operations = [
        migrations.DeleteModel(
            name="IVRCall",
        ),
    ]