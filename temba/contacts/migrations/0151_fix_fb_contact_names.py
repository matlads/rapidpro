# Generated by Django 4.0.2 on 2022-02-24 19:12

import requests

from django.db import migrations


def populate_fb_contact_names(apps, schema_editor):  # pragma: no cover
    Org = apps.get_model("orgs", "Org")
    ContactURN = apps.get_model("contacts", "ContactURN")

    orgs = Org.objects.filter(is_active=True, is_anon=False)

    for org in orgs:
        num_updated = 0

        fb_urns = (
            ContactURN.objects.filter(contact__is_active=True, org=org, scheme="facebook")
            .exclude(channel=None)
            .exclude(channel__is_active=False)
            .select_related("channel", "contact")
        )
        for fb_urn in fb_urns:
            fb_path = fb_urn.path

            access_token = fb_urn.channel.config["auth_token"]
            urn_url = f"https://graph.facebook.com/v12.0/{fb_path}?access_token={access_token}"
            response = requests.get(urn_url)
            if response.status_code == 200:
                resp_json = response.json()
                name = f"{resp_json.get('first_name')} {resp_json.get('last_name')}"
                if name and name != fb_urn.contact.name:
                    contact = fb_urn.contact
                    contact.name = name
                    contact.save(update_fields=("name", "modified_on"))
                    num_updated += 1

        if num_updated > 0:
            print(f"Updated {num_updated} contacts for org #{org.pk}, {org.name}")


def reverse(apps, schema_editor):  # pragma: no cover
    pass


def apply_manual():  # pragma: no cover
    from django.apps import apps

    populate_fb_contact_names(apps, None)


class Migration(migrations.Migration):

    dependencies = [
        ("contacts", "0150_full_release_deleted_contacts"),
    ]

    operations = [migrations.RunPython(populate_fb_contact_names, reverse)]
