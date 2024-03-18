from unittest.mock import patch
from zoneinfo import ZoneInfo

import requests

from temba.channels.models import Channel
from temba.channels.types.whatsapp_legacy.type import (
    CONFIG_FB_ACCESS_TOKEN,
    CONFIG_FB_BUSINESS_ID,
    CONFIG_FB_NAMESPACE,
    CONFIG_FB_TEMPLATE_LIST_DOMAIN,
)
from temba.notifications.incidents.builtin import ChannelTemplatesFailedIncidentType
from temba.notifications.models import Incident
from temba.orgs.models import Org, OrgRole
from temba.request_logs.models import HTTPLog
from temba.templates.models import Template, TemplateTranslation
from temba.tests import TembaTest
from temba.tests.requests import MockResponse

from . import update_api_version
from .tasks import (
    _calculate_variable_count,
    parse_whatsapp_language,
    refresh_whatsapp_templates,
    update_local_templates,
)


class WhatsAppUtilsTest(TembaTest):
    def test_parse_whatsapp_language(self):
        self.assertEqual("eng", parse_whatsapp_language("en"))
        self.assertEqual("eng-US", parse_whatsapp_language("en_US"))
        self.assertEqual("fil", parse_whatsapp_language("fil"))

    def test_calculate_variable_count(self):
        self.assertEqual(2, _calculate_variable_count("Hi {{1}} how are you? {{2}}"))
        self.assertEqual(2, _calculate_variable_count("Hi {{1}} how are you? {{2}} {{1}}"))
        self.assertEqual(0, _calculate_variable_count("Hi there."))

    def test_update_local_templates_whatsapp(self):
        # channel has namespace in the channel config
        channel = self.create_channel("WA", "channel", "1234", config={"fb_namespace": "foo_namespace"})

        self.assertEqual(0, Template.objects.filter(org=self.org).count())
        self.assertEqual(0, TemplateTranslation.objects.filter(channel=channel).count())

        # no namespace in template data, use channel config namespace
        WA_templates_data = [
            {
                "name": "hello",
                "components": [{"type": "BODY", "text": "Hello {{1}}"}],
                "language": "en",
                "status": "PENDING",
                "category": "ISSUE_RESOLUTION",
                "id": "1234",
            },
            {
                "name": "hello",
                "components": [{"type": "BODY", "text": "Hi {{1}}"}],
                "language": "en_GB",
                "status": "PENDING",
                "category": "ISSUE_RESOLUTION",
                "id": "4321",
            },
            {
                "name": "hello",
                "components": [{"type": "BODY", "text": "Bonjour {{1}}"}],
                "language": "fr",
                "status": "APPROVED",
                "category": "ISSUE_RESOLUTION",
                "id": "5678",
            },
            {
                "name": "goodbye",
                "components": [{"type": "BODY", "text": "Goodbye {{1}}, see you on {{2}}. See you later {{1}}"}],
                "language": "en",
                "status": "PENDING",
                "category": "ISSUE_RESOLUTION",
                "id": "9012",
            },
            {
                "name": "workout_activity",
                "components": [
                    {"type": "HEADER", "text": "Workout challenge week extra points!"},
                    {
                        "type": "BODY",
                        "text": "Hey {{1}}, Week {{2}} workout is out now. Get your discount of {{3}} for the next workout by sharing this program to 3 people.",
                    },
                    {"type": "FOOTER", "text": "Remember to drink water."},
                ],
                "language": "en",
                "status": "PENDING",
                "category": "ISSUE_RESOLUTION",
                "id": "9014",
            },
            {
                "name": "workout_activity_with_variables",
                "components": [
                    {"type": "HEADER", "text": "Workout challenge week {{2}}, {{4}} extra points!"},
                    {
                        "type": "BODY",
                        "text": "Hey {{1}}, Week {{2}} workout is out now. Get your discount of {{3}} for the next workout by sharing this program to 3 people.",
                    },
                    {"type": "FOOTER", "text": "Remember to drink water."},
                ],
                "language": "en",
                "status": "PENDING",
                "category": "ISSUE_RESOLUTION",
                "id": "9015",
            },
            {
                "name": "missing_text_component",
                "components": [{"type": "HEADER", "format": "IMAGE", "example": {"header_handle": ["FOO"]}}],
                "language": "en",
                "status": "APPROVED",
                "category": "ISSUE_RESOLUTION",
                "id": "1235",
            },
            {
                "name": "invalid_component",
                "components": [{"type": "RANDOM", "text": "Bonjour {{1}}"}],
                "language": "fr",
                "status": "APPROVED",
                "category": "ISSUE_RESOLUTION",
                "id": "1233",
            },
            {
                "name": "invalid_status",
                "components": [{"type": "BODY", "text": "This is an unknown status, it will be ignored"}],
                "language": "en",
                "status": "UNKNOWN",
                "category": "ISSUE_RESOLUTION",
                "id": "9012",
            },
            {
                "name": "order_template",
                "components": [
                    {
                        "type": "HEADER",
                        "format": "IMAGE",
                        "example": {"header_handle": [r"http://example.com/test.jpg"]},
                    },
                    {
                        "type": "BODY",
                        "text": "Sorry your order {{1}} took longer to deliver than expected.\nWe'll notify you about updates in the next {{2}} days.\n\nDo you have more question?",
                        "example": {"body_text": [["#123 for shoes", "3"]]},
                    },
                    {"type": "FOOTER", "text": "Thanks for your patience"},
                    {
                        "type": "BUTTONS",
                        "buttons": [
                            {"type": "QUICK_REPLY", "text": "Yes"},
                            {"type": "QUICK_REPLY", "text": "No"},
                            {"type": "PHONE_NUMBER", "text": "Call center", "phone_number": "+1234"},
                            {
                                "type": "URL",
                                "text": "Check website",
                                "url": r"https:\/\/example.com\/?wa_customer={{1}}",
                                "example": [r"https:\/\/example.com\/?wa_customer=id_123"],
                            },
                            {
                                "type": "URL",
                                "text": "Check website",
                                "url": r"https:\/\/example.com\/help",
                                "example": [r"https:\/\/example.com\/help"],
                            },
                        ],
                    },
                ],
                "language": "en",
                "status": "APPROVED",
                "category": "UTILITY",
                "id": "9020",
            },
            {
                "category": "UTILITY",
                "components": [
                    {"add_security_recommendation": "True", "type": "BODY"},
                    {"type": "FOOTER"},
                    {"buttons": [{"otp_type": "COPY_CODE", "text": "copy", "type": "OTP"}], "type": "BUTTONS"},
                ],
                "language": "fr",
                "name": "login",
                "status": "approved",
                "id": "9030",
            },
        ]

        update_local_templates(channel, WA_templates_data)

        self.assertEqual(8, Template.objects.filter(org=self.org).count())
        self.assertEqual(10, TemplateTranslation.objects.filter(channel=channel).count())
        self.assertEqual(10, TemplateTranslation.objects.filter(channel=channel, namespace="foo_namespace").count())
        self.assertEqual(
            4,
            TemplateTranslation.objects.filter(
                channel=channel, status=TemplateTranslation.STATUS_UNSUPPORTED_COMPONENTS
            ).count(),
        )

        ct = TemplateTranslation.objects.get(template__name="goodbye", is_active=True)
        self.assertEqual(2, ct.variable_count)
        self.assertEqual("Goodbye {{1}}, see you on {{2}}. See you later {{1}}", ct.content)
        self.assertEqual("eng", ct.locale)
        self.assertEqual(TemplateTranslation.STATUS_PENDING, ct.status)
        self.assertEqual("goodbye (eng) P: Goodbye {{1}}, see you on {{2}}. See you later {{1}}", str(ct))
        self.assertEqual("foo_namespace", ct.namespace)
        self.assertEqual(
            {
                "body": {
                    "content": "Goodbye {{1}}, see you on {{2}}. See you later {{1}}",
                    "type": "body",
                    "params": [{"type": "text"}, {"type": "text"}, {"type": "text"}],
                }
            },
            ct.components,
        )
        self.assertEqual({"body": [{"type": "text"}, {"type": "text"}, {"type": "text"}]}, ct.params)

        ct = TemplateTranslation.objects.get(template__name="workout_activity", is_active=True)
        self.assertEqual(3, ct.variable_count)
        self.assertEqual(
            "Workout challenge week extra points!\n\nHey {{1}}, Week {{2}} workout is out now. Get your discount of {{3}} for the next workout by sharing this program to 3 people.\n\nRemember to drink water.",
            ct.content,
        )
        self.assertEqual("eng", ct.locale)
        self.assertEqual(TemplateTranslation.STATUS_PENDING, ct.status)
        self.assertEqual("foo_namespace", ct.namespace)
        self.assertEqual(
            {
                "header": {"content": "Workout challenge week extra points!", "type": "header", "params": []},
                "body": {
                    "content": "Hey {{1}}, Week {{2}} workout is out now. Get your discount of {{3}} for the next workout by sharing this program to 3 people.",
                    "type": "body",
                    "params": [{"type": "text"}, {"type": "text"}, {"type": "text"}],
                },
                "footer": {"content": "Remember to drink water.", "type": "footer", "params": []},
            },
            ct.components,
        )
        self.assertEqual({"body": [{"type": "text"}, {"type": "text"}, {"type": "text"}]}, ct.params)

        ct = TemplateTranslation.objects.get(template__name="invalid_component", is_active=True)
        self.assertEqual("fra", ct.locale)
        self.assertEqual(TemplateTranslation.STATUS_UNSUPPORTED_COMPONENTS, ct.status)
        self.assertEqual("foo_namespace", ct.namespace)
        self.assertEqual(
            {"random": {"content": "Bonjour {{1}}", "type": "random", "params": []}},
            ct.components,
        )
        self.assertEqual({}, ct.params)

        ct = TemplateTranslation.objects.get(template__name="login", is_active=True)
        self.assertEqual("fra", ct.locale)
        self.assertEqual(TemplateTranslation.STATUS_UNSUPPORTED_COMPONENTS, ct.status)
        self.assertEqual("foo_namespace", ct.namespace)
        self.assertEqual(
            {
                "body": {"content": "", "type": "body", "params": []},
                "footer": {"content": "", "type": "footer", "params": []},
                "button.0": {"content": "copy", "type": "otp", "params": []},
            },
            ct.components,
        )
        self.assertEqual({}, ct.params)

        ct = TemplateTranslation.objects.get(template__name="order_template", is_active=True)
        self.assertEqual("eng", ct.locale)
        self.assertEqual(TemplateTranslation.STATUS_UNSUPPORTED_COMPONENTS, ct.status)
        self.assertEqual("foo_namespace", ct.namespace)
        self.assertEqual(
            {
                "header": {"content": "", "type": "header", "params": [{"type": "image"}]},
                "body": {
                    "content": "Sorry your order {{1}} took longer to deliver than expected.\nWe'll notify you about updates in the next {{2}} days.\n\nDo you have more question?",
                    "type": "body",
                    "params": [{"type": "text"}, {"type": "text"}],
                },
                "footer": {"content": "Thanks for your patience", "type": "footer", "params": []},
                "button.0": {"content": "Yes", "type": "quick_reply", "params": []},
                "button.1": {"content": "No", "type": "quick_reply", "params": []},
                "button.2": {"content": "Call center", "type": "phone_number", "params": []},
                "button.3": {
                    "content": r"https:\/\/example.com\/?wa_customer={{1}}",
                    "display": "Check website",
                    "type": "url",
                    "params": [{"type": "url"}],
                },
                "button.4": {
                    "content": r"https:\/\/example.com\/help",
                    "type": "url",
                    "display": "Check website",
                    "params": [],
                },
            },
            ct.components,
        )
        self.assertEqual(
            {
                "header": [{"type": "image"}],
                "body": [{"type": "text"}, {"type": "text"}],
                "button.3": [{"type": "url"}],
            },
            ct.params,
        )

    def test_update_local_templates_dialog360(self):
        # no namespace in channel config
        channel = self.create_channel("D3", "channel", "1234", config={})

        # no template id, use language/name as external ID
        # template data have namespaces
        D3_templates_data = [
            {
                "name": "hello",
                "components": [{"type": "BODY", "text": "Hello {{1}}"}],
                "language": "en",
                "status": "pending",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "hello",
                "components": [{"type": "BODY", "text": "Hi {{1}}"}],
                "language": "en_GB",
                "status": "pending",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "hello",
                "components": [{"type": "BODY", "text": "Bonjour {{1}}"}],
                "language": "fr",
                "status": "approved",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "goodbye",
                "components": [{"type": "BODY", "text": "Goodbye {{1}}, see you on {{2}}. See you later {{1}}"}],
                "language": "en",
                "status": "PENDING",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "workout_activity",
                "components": [
                    {"type": "HEADER", "text": "Workout challenge week extra points!"},
                    {
                        "type": "BODY",
                        "text": "Hey {{1}}, Week {{2}} workout is out now. Get your discount of {{3}} for the next workout by sharing this program to 3 people.",
                    },
                    {"type": "FOOTER", "text": "Remember to drink water."},
                ],
                "language": "en",
                "status": "PENDING",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "workout_activity_with_variables",
                "components": [
                    {"type": "HEADER", "text": "Workout challenge week {{2}}, {{4}} extra points!"},
                    {
                        "type": "BODY",
                        "text": "Hey {{1}}, Week {{2}} workout is out now. Get your discount of {{3}} for the next workout by sharing this program to 3 people.",
                    },
                    {"type": "FOOTER", "text": "Remember to drink water."},
                ],
                "language": "en",
                "status": "PENDING",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "missing_text_component",
                "components": [{"type": "HEADER", "format": "IMAGE", "example": {"header_handle": ["FOO"]}}],
                "language": "en",
                "status": "APPROVED",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "invalid_component",
                "components": [{"type": "RANDOM", "text": "Bonjour {{1}}"}],
                "language": "fr",
                "status": "APPROVED",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "invalid_status",
                "components": [{"type": "BODY", "text": "This is an unknown status, it will be ignored"}],
                "language": "en",
                "status": "UNKNOWN",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "invalid_language",
                "components": [{"type": "BODY", "text": "This is an unknown language, it will be ignored"}],
                "language": "kli",
                "status": "APPROVED",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "ISSUE_RESOLUTION",
            },
            {
                "name": "this_is_template_has_a_very_long_name,_and_not_having_an_id,_we_generate_the_external_id_from_the_name_and_truncate_that_to_64_characters",
                "components": [
                    {
                        "type": "BODY",
                        "text": "This is template has a very long name, and not having an id, we generate the external_id from the name and truncate that to 64 characters",
                    }
                ],
                "language": "en_US",
                "status": "APPROVED",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "UTILITY",
            },
            {
                "name": "order_template",
                "components": [
                    {
                        "type": "HEADER",
                        "format": "IMAGE",
                        "example": {"header_handle": [r"http://example.com/test.jpg"]},
                    },
                    {
                        "type": "BODY",
                        "text": "Sorry your order {{1}} took longer to deliver than expected.\nWe'll notify you about updates in the next {{2}} days.\n\nDo you have more question?",
                        "example": {"body_text": [["#123 for shoes", "3"]]},
                    },
                    {"type": "FOOTER", "text": "Thanks for your patience"},
                    {
                        "type": "BUTTONS",
                        "buttons": [
                            {"type": "QUICK_REPLY", "text": "Yes"},
                            {"type": "QUICK_REPLY", "text": "No"},
                            {"type": "PHONE_NUMBER", "text": "Call center", "phone_number": "+1234"},
                            {
                                "type": "URL",
                                "text": "Check website",
                                "url": r"https:\/\/example.com\/?wa_customer={{1}}",
                                "example": [r"https:\/\/example.com\/?wa_customer=id_123"],
                            },
                        ],
                    },
                ],
                "language": "en",
                "status": "APPROVED",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "category": "UTILITY",
            },
            {
                "category": "UTILITY",
                "components": [
                    {"add_security_recommendation": "True", "type": "BODY"},
                    {"type": "FOOTER"},
                    {"buttons": [{"otp_type": "COPY_CODE", "text": "copy", "type": "OTP"}], "type": "BUTTONS"},
                ],
                "language": "fr",
                "name": "login",
                "namespace": "xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx",
                "rejected_reason": "NONE",
                "status": "approved",
            },
        ]

        update_local_templates(channel, D3_templates_data)

        self.assertEqual(10, Template.objects.filter(org=self.org).count())
        self.assertEqual(12, TemplateTranslation.objects.filter(channel=channel).count())
        self.assertEqual(0, TemplateTranslation.objects.filter(channel=channel, namespace="").count())
        self.assertEqual(0, TemplateTranslation.objects.filter(channel=channel, namespace=None).count())
        self.assertEqual(
            sorted(
                [
                    "en/hello",
                    "en_GB/hello",
                    "fr/hello",
                    "en/goodbye",
                    "en/order_template",
                    "en_US/this_is_template_has_a_very_long_name,_and_not_having_an_i",
                    "en/workout_activity",
                    "kli/invalid_language",
                    "en/missing_text_component",
                    "en/workout_activity_with_variables",
                    "fr/invalid_component",
                    "fr/login",
                ]
            ),
            sorted(
                list(
                    TemplateTranslation.objects.filter(channel=channel, is_active=True).values_list(
                        "external_id", flat=True
                    )
                )
            ),
        )

        self.assertEqual(
            4,
            TemplateTranslation.objects.filter(
                channel=channel, status=TemplateTranslation.STATUS_UNSUPPORTED_COMPONENTS
            ).count(),
        )
        self.assertEqual(
            [
                "en/missing_text_component",
                "en/order_template",
                "fr/invalid_component",
                "fr/login",
            ],
            list(
                TemplateTranslation.objects.filter(
                    channel=channel, status=TemplateTranslation.STATUS_UNSUPPORTED_COMPONENTS
                ).values_list("external_id", flat=True)
            ),
        )

        tt = TemplateTranslation.objects.filter(channel=channel, external_id="fr/invalid_component").first()
        self.assertEqual(TemplateTranslation.STATUS_UNSUPPORTED_COMPONENTS, tt.status)

        tt = TemplateTranslation.objects.filter(channel=channel, external_id="en/hello").first()
        self.assertEqual("xxxxxxxx_xxxx_xxxx_xxxx_xxxxxxxxxxxx", tt.namespace)

    @patch("temba.channels.types.whatsapp_legacy.WhatsAppLegacyType.check_health")
    def test_update_api_version_whatsapp(self, mock_health):
        mock_health.return_value = MockResponse(200, '{"meta": {"api_status": "stable", "version": "v2.35.2"}}')

        Channel.objects.all().delete()
        channel = self.create_channel(
            "WA",
            "WhatsApp: 1234",
            "1234",
            config={
                Channel.CONFIG_BASE_URL: "https://nyaruka.com/whatsapp",
                Channel.CONFIG_USERNAME: "temba",
                Channel.CONFIG_PASSWORD: "tembapasswd",
                Channel.CONFIG_AUTH_TOKEN: "authtoken123",
                CONFIG_FB_BUSINESS_ID: "1234",
                CONFIG_FB_ACCESS_TOKEN: "token123",
                CONFIG_FB_NAMESPACE: "my-custom-app",
                CONFIG_FB_TEMPLATE_LIST_DOMAIN: "graph.facebook.com",
            },
        )

        update_api_version(channel)
        mock_health.assert_called_with(channel)

        channel.refresh_from_db()
        self.assertDictContainsSubset({"version": "v2.35.2"}, channel.config)

        self.assertEqual(0, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_CHECK_HEALTH).count())
        mock_health.side_effect = [requests.RequestException(response=MockResponse(401, "{}"))]
        update_api_version(channel)
        self.assertEqual(1, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_CHECK_HEALTH).count())

    @patch("temba.channels.types.dialog360_legacy.Dialog360LegacyType.check_health")
    def test_update_api_version_dialog360(self, mock_health):
        mock_health.return_value = MockResponse(200, '{"meta": {"api_status": "stable", "version": "2.35.4"}}')

        Channel.objects.all().delete()
        channel = self.create_channel(
            "D3",
            "360Dialog channel",
            address="1234",
            country="BR",
            config={
                Channel.CONFIG_BASE_URL: "https://example.com/whatsapp",
                Channel.CONFIG_AUTH_TOKEN: "123456789",
            },
        )

        update_api_version(channel)
        mock_health.assert_called_with(channel)

        channel.refresh_from_db()
        self.assertDictContainsSubset({"version": "v2.35.4"}, channel.config)

        self.assertEqual(0, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_CHECK_HEALTH).count())
        mock_health.side_effect = [requests.RequestException(response=MockResponse(401, "{}"))]
        update_api_version(channel)
        self.assertEqual(1, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_CHECK_HEALTH).count())

    @patch("temba.utils.whatsapp.tasks.update_local_templates")
    @patch("temba.channels.types.dialog360.Dialog360Type.fetch_templates")
    @patch("temba.channels.types.dialog360_legacy.Dialog360LegacyType.fetch_templates")
    def test_refresh_templates(self, mock_d3_fetch_templates, mock_d3c_fetch_templates, mock_update_local):
        org3 = Org.objects.create(
            name="Nyaruka 3",
            timezone=ZoneInfo("Africa/Kigali"),
            flow_languages=["eng", "kin"],
            created_by=self.admin,
            modified_by=self.admin,
        )
        org3.initialize()
        org3.add_user(self.admin, OrgRole.ADMINISTRATOR)
        org3.suspend()

        org4 = Org.objects.create(
            name="Nyaruka 4",
            timezone=ZoneInfo("Africa/Kigali"),
            flow_languages=["eng", "kin"],
            created_by=self.admin,
            modified_by=self.admin,
        )
        org4.initialize()
        org4.add_user(self.admin, OrgRole.ADMINISTRATOR)
        org4.release(self.admin)

        # channels on suspended org are ignored
        self.create_channel(
            "D3",
            "360Dialog channel",
            address="234",
            country="BR",
            config={
                Channel.CONFIG_BASE_URL: "https://example.com/whatsapp",
                Channel.CONFIG_AUTH_TOKEN: "123456789",
            },
            org=org3,
        )

        # channels on inactive org are ignored
        self.create_channel(
            "D3",
            "360Dialog channel",
            address="345",
            country="BR",
            config={
                Channel.CONFIG_BASE_URL: "https://example.com/whatsapp",
                Channel.CONFIG_AUTH_TOKEN: "123456789",
            },
            org=org4,
        )

        d3c_channel = self.create_channel(
            "D3C",
            "360Dialog channel",
            address="1234",
            country="BR",
            config={
                Channel.CONFIG_BASE_URL: "https://waba-v2.360dialog.io",
                Channel.CONFIG_AUTH_TOKEN: "123456789",
            },
        )
        self.create_channel(
            "D3",
            "360Dialog channel",
            address="1234",
            country="BR",
            config={
                Channel.CONFIG_BASE_URL: "https://example.com/whatsapp",
                Channel.CONFIG_AUTH_TOKEN: "123456789",
            },
        )

        def mock_fetch(ch):
            HTTPLog.objects.create(
                org=ch.org, channel=ch, log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, request_time=0, is_error=False
            )
            return [{"name": "hello"}]

        def mock_fail_fetch(ch):
            HTTPLog.objects.create(
                org=ch.org, channel=ch, log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, request_time=0, is_error=True
            )
            raise requests.ConnectionError("timeout")

        mock_d3_fetch_templates.side_effect = mock_fetch
        mock_d3c_fetch_templates.side_effect = mock_fetch
        mock_update_local.return_value = None

        refresh_whatsapp_templates()

        self.assertEqual(1, mock_d3_fetch_templates.call_count)
        self.assertEqual(1, mock_d3c_fetch_templates.call_count)
        self.assertEqual(2, mock_update_local.call_count)
        self.assertEqual(0, Incident.objects.filter(incident_type=ChannelTemplatesFailedIncidentType.slug).count())

        # if one channel fails, others continue
        mock_d3c_fetch_templates.side_effect = mock_fail_fetch

        refresh_whatsapp_templates()

        self.assertEqual(2, mock_d3_fetch_templates.call_count)
        self.assertEqual(2, mock_d3c_fetch_templates.call_count)
        self.assertEqual(3, mock_update_local.call_count)

        # one failure isn't enough to create an incident
        self.assertEqual(0, Incident.objects.filter(incident_type=ChannelTemplatesFailedIncidentType.slug).count())

        # but 5 will be
        refresh_whatsapp_templates()
        refresh_whatsapp_templates()
        refresh_whatsapp_templates()
        refresh_whatsapp_templates()

        self.assertEqual(
            1,
            Incident.objects.filter(
                incident_type=ChannelTemplatesFailedIncidentType.slug, channel=d3c_channel, ended_on=None
            ).count(),
        )

        # a successful fetch will clear it
        mock_d3c_fetch_templates.side_effect = mock_fetch

        refresh_whatsapp_templates()

        self.assertEqual(
            0,
            Incident.objects.filter(
                incident_type=ChannelTemplatesFailedIncidentType.slug, channel=d3c_channel, ended_on=None
            ).count(),
        )

        # other exception logged to sentry
        mock_d3c_fetch_templates.side_effect = Exception("boom")
        with patch("logging.Logger.error") as mock_log_error:
            refresh_whatsapp_templates()
            self.assertEqual(1, mock_log_error.call_count)
            self.assertEqual("Error refreshing whatsapp templates: boom", mock_log_error.call_args[0][0])
