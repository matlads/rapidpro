# Generated by Django 4.2.2 on 2023-07-12 21:22

from django.db import migrations


def move_twilio_sid(apps, schema_editor):
    Channel = apps.get_model("channels", "Channel")

    num_updated = 0

    for ch in Channel.objects.filter(channel_type="T", is_active=True).exclude(bod=None):
        if not ch.config.get("number_sid"):
            ch.config["number_sid"] = ch.bod
            ch.save(update_fields=("config",))
            num_updated += 1

    if num_updated:
        print(f"Updated {num_updated} Twilio channels to not use deprecated bod field")


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("channels", "0168_channel_log_policy")]

    operations = [migrations.RunPython(move_twilio_sid, reverse)]
