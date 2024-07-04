from django.urls import reverse
from django.utils import timezone

from temba.api.tests import APITestMixin
from temba.contacts.models import ContactExport
from temba.notifications.types import ExportFinishedNotificationType
from temba.templates.models import TemplateTranslation
from temba.tests import TembaTest, matchers
from temba.tickets.models import TicketExport

NUM_BASE_QUERIES = 4  # number of queries required for any request (internal API is session only)


class EndpointsTest(APITestMixin, TembaTest):
    def test_locations(self):
        endpoint_url = reverse("api.internal.locations") + ".json"

        self.assertGetNotPermitted(endpoint_url, [None])
        self.assertPostNotAllowed(endpoint_url)
        self.assertDeleteNotAllowed(endpoint_url)

        # no country, no results
        self.assertGet(endpoint_url + "?level=state", [self.agent], results=[])

        self.setUpLocations()

        self.assertGet(
            endpoint_url + "?level=state",
            [self.agent],
            results=[
                {"osm_id": "171591", "name": "Eastern Province", "path": "Rwanda > Eastern Province"},
                {"osm_id": "1708283", "name": "Kigali City", "path": "Rwanda > Kigali City"},
            ],
        )
        self.assertGet(
            endpoint_url + "?level=district",
            [self.user],
            results=[
                {"osm_id": "R1711131", "name": "Gatsibo", "path": "Rwanda > Eastern Province > Gatsibo"},
                {"osm_id": "1711163", "name": "Kayônza", "path": "Rwanda > Eastern Province > Kayônza"},
                {"osm_id": "3963734", "name": "Nyarugenge", "path": "Rwanda > Kigali City > Nyarugenge"},
                {"osm_id": "1711142", "name": "Rwamagana", "path": "Rwanda > Eastern Province > Rwamagana"},
            ],
        )

        # can query on name
        self.assertGet(
            endpoint_url + "?level=district&query=ga",
            [self.editor],
            results=[
                {"osm_id": "R1711131", "name": "Gatsibo", "path": "Rwanda > Eastern Province > Gatsibo"},
                {"osm_id": "1711142", "name": "Rwamagana", "path": "Rwanda > Eastern Province > Rwamagana"},
            ],
        )

        # or alias
        self.assertGet(
            endpoint_url + "?level=state&query=kigari",
            [self.admin],
            results=[
                {"osm_id": "1708283", "name": "Kigali City", "path": "Rwanda > Kigali City"},
            ],
        )

        # but not aliases in other orgs
        self.assertGet(endpoint_url + "?level=state&query=Chigali", [self.agent], results=[])

        # invalid level, no results
        self.assertGet(endpoint_url + "?level=hood", [self.agent], results=[])

    def test_notifications(self):
        endpoint_url = reverse("api.internal.notifications") + ".json"

        self.assertPostNotAllowed(endpoint_url)

        # simulate an export finishing
        export1 = ContactExport.create(self.org, self.admin)
        ExportFinishedNotificationType.create(export1)

        # simulate an export by another user finishing
        export2 = TicketExport.create(self.org, self.editor, start_date=timezone.now(), end_date=timezone.now())
        ExportFinishedNotificationType.create(export2)

        # and org being suspended
        self.org.suspend()

        self.assertGet(
            endpoint_url,
            [self.admin],
            results=[
                {
                    "type": "incident:started",
                    "created_on": matchers.ISODate(),
                    "target_url": "/incident/",
                    "is_seen": False,
                    "incident": {
                        "type": "org:suspended",
                        "started_on": matchers.ISODate(),
                        "ended_on": None,
                    },
                },
                {
                    "type": "export:finished",
                    "created_on": matchers.ISODate(),
                    "target_url": f"/export/download/{export1.uuid}/",
                    "is_seen": False,
                    "export": {"type": "contact", "num_records": None},
                },
            ],
        )

        # notifications are user specific
        self.assertGet(
            endpoint_url,
            [self.editor],
            results=[
                {
                    "type": "export:finished",
                    "created_on": matchers.ISODate(),
                    "target_url": f"/export/download/{export2.uuid}/",
                    "is_seen": False,
                    "export": {"type": "ticket", "num_records": None},
                },
            ],
        )

        # a DELETE marks all notifications as seen
        self.assertDelete(endpoint_url, self.admin)

        self.assertEqual(0, self.admin.notifications.filter(is_seen=False).count())
        self.assertEqual(2, self.admin.notifications.filter(is_seen=True).count())
        self.assertEqual(1, self.editor.notifications.filter(is_seen=False).count())

    def test_templates(self):
        endpoint_url = reverse("api.internal.templates") + ".json"

        self.assertGetNotPermitted(endpoint_url, [None, self.agent])
        self.assertPostNotAllowed(endpoint_url)
        self.assertDeleteNotAllowed(endpoint_url)

        org2channel = self.create_channel("A", "Org2Channel", "123456", country="RW", org=self.org2)

        # create some templates
        tpl1 = TemplateTranslation.get_or_create(
            self.channel,
            "hello",
            locale="eng-US",
            status=TemplateTranslation.STATUS_APPROVED,
            external_id="1234",
            external_locale="en_US",
            namespace="foo_namespace",
            components=[
                {
                    "name": "body",
                    "type": "body/text",
                    "content": "Hi {{1}}",
                    "variables": {"1": 0},
                    "params": [{"type": "text"}],
                }
            ],
            variables=[{"type": "text"}],
        ).template
        TemplateTranslation.get_or_create(
            self.channel,
            "hello",
            locale="fra-FR",
            status=TemplateTranslation.STATUS_PENDING,
            external_id="5678",
            external_locale="fr_FR",
            namespace="foo_namespace",
            components=[
                {
                    "name": "body",
                    "type": "body/text",
                    "content": "Bonjour {{1}}",
                    "variables": {"1": 0},
                    "params": [{"type": "text"}],
                }
            ],
            variables=[{"type": "text"}],
        )
        tt = TemplateTranslation.get_or_create(
            self.channel,
            "hello",
            locale="afr-ZA",
            status=TemplateTranslation.STATUS_APPROVED,
            external_id="9012",
            external_locale="af_ZA",
            namespace="foo_namespace",
            components=[
                {
                    "name": "body",
                    "type": "body/text",
                    "content": "This is a template translation for a deleted channel {{1}}",
                    "variables": {"1": 0},
                    "params": [{"type": "text"}],
                }
            ],
            variables=[{"type": "text"}],
        )
        tt.is_active = False
        tt.save()

        tpl2 = TemplateTranslation.get_or_create(
            self.channel,
            "goodbye",
            locale="eng-US",
            status=TemplateTranslation.STATUS_PENDING,
            external_id="6789",
            external_locale="en_US",
            namespace="foo_namespace",
            components=[
                {
                    "name": "body",
                    "type": "body/text",
                    "content": "Goodbye {{1}}",
                    "variables": {"1": 0},
                    "params": [{"type": "text"}],
                }
            ],
            variables=[{"type": "text"}],
        ).template

        # templates on other org to test filtering
        TemplateTranslation.get_or_create(
            org2channel,
            "goodbye",
            locale="eng-US",
            status=TemplateTranslation.STATUS_APPROVED,
            external_id="1234",
            external_locale="en_US",
            namespace="bar_namespace",
            components=[
                {
                    "name": "body",
                    "type": "body/text",
                    "content": "Goodbye {{1}}",
                    "variables": {"1": 0},
                    "params": [{"type": "text"}],
                }
            ],
            variables=[{"type": "text"}],
        )
        TemplateTranslation.get_or_create(
            org2channel,
            "goodbye",
            locale="fra-FR",
            status=TemplateTranslation.STATUS_PENDING,
            external_id="5678",
            external_locale="fr_FR",
            namespace="bar_namespace",
            components=[
                {
                    "name": "body",
                    "type": "body/text",
                    "content": "Salut {{1}}",
                    "variables": {"1": 0},
                    "params": [{"type": "text"}],
                }
            ],
            variables=[{"type": "text"}],
        )

        tpl1.refresh_from_db()
        tpl2.refresh_from_db()

        # no filtering
        self.assertGet(
            endpoint_url,
            [self.user, self.editor],
            results=[
                {
                    "name": "goodbye",
                    "uuid": str(tpl2.uuid),
                    "translations": [
                        {
                            "channel": {"name": self.channel.name, "uuid": self.channel.uuid},
                            "locale": "eng-US",
                            "namespace": "foo_namespace",
                            "status": "pending",
                            "components": [
                                {
                                    "name": "body",
                                    "type": "body/text",
                                    "content": "Goodbye {{1}}",
                                    "variables": {"1": 0},
                                    "params": [{"type": "text"}],
                                }
                            ],
                            "variables": [{"type": "text"}],
                        },
                    ],
                    "created_on": matchers.ISODate(),
                    "modified_on": matchers.ISODate(),
                },
                {
                    "name": "hello",
                    "uuid": str(tpl1.uuid),
                    "translations": [
                        {
                            "channel": {"name": self.channel.name, "uuid": self.channel.uuid},
                            "locale": "eng-US",
                            "namespace": "foo_namespace",
                            "status": "approved",
                            "components": [
                                {
                                    "name": "body",
                                    "type": "body/text",
                                    "content": "Hi {{1}}",
                                    "variables": {"1": 0},
                                    "params": [{"type": "text"}],
                                }
                            ],
                            "variables": [{"type": "text"}],
                        },
                        {
                            "channel": {"name": self.channel.name, "uuid": self.channel.uuid},
                            "locale": "fra-FR",
                            "namespace": "foo_namespace",
                            "status": "pending",
                            "components": [
                                {
                                    "name": "body",
                                    "type": "body/text",
                                    "content": "Bonjour {{1}}",
                                    "variables": {"1": 0},
                                    "params": [{"type": "text"}],
                                }
                            ],
                            "variables": [{"type": "text"}],
                        },
                    ],
                    "created_on": matchers.ISODate(),
                    "modified_on": matchers.ISODate(),
                },
            ],
            num_queries=NUM_BASE_QUERIES + 3,
        )
