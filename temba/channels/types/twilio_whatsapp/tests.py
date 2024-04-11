import json
from unittest.mock import patch

from requests import RequestException
from twilio.base.exceptions import TwilioRestException

from django.urls import reverse

from temba.channels.models import Channel
from temba.request_logs.models import HTTPLog
from temba.tests import TembaTest
from temba.tests.requests import MockResponse
from temba.tests.twilio import MockRequestValidator, MockTwilioClient

from .type import TwilioWhatsappType


class TwilioWhatsappTypeTest(TembaTest):
    @patch("temba.channels.types.twilio_whatsapp.views.TwilioClient", MockTwilioClient)
    @patch("temba.channels.types.twilio.views.TwilioClient", MockTwilioClient)
    @patch("twilio.request_validator.RequestValidator", MockRequestValidator)
    def test_claim(self):
        self.login(self.admin)

        claim_twilio = reverse("channels.types.twilio_whatsapp.claim")

        # remove any existing channels
        self.org.channels.update(is_active=False)

        # make sure twilio is on the claim page
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, "Twilio")

        response = self.client.get(claim_twilio)
        self.assertEqual(response.status_code, 302)
        response = self.client.get(claim_twilio, follow=True)
        self.assertEqual(response.request["PATH_INFO"], reverse("channels.types.twilio.connect"))

        # attach a Twilio account to the session
        session = self.client.session
        session[TwilioWhatsappType.SESSION_ACCOUNT_SID] = "account-sid"
        session[TwilioWhatsappType.SESSION_AUTH_TOKEN] = "account-token"
        session.save()

        # hit the claim page, should now have a claim twilio link
        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, claim_twilio)

        response = self.client.get(claim_twilio)
        self.assertIn("account_trial", response.context)
        self.assertFalse(response.context["account_trial"])

        with patch("temba.channels.types.twilio_whatsapp.views.ClaimView.get_twilio_client") as mock_get_twilio_client:
            mock_get_twilio_client.return_value = None

            response = self.client.get(claim_twilio)
            self.assertRedirects(response, f'{reverse("channels.types.twilio.connect")}?claim_type=twilio_whatsapp')

            mock_get_twilio_client.side_effect = TwilioRestException(
                401, "http://twilio", msg="Authentication Failure", code=20003
            )

            response = self.client.get(claim_twilio)
            self.assertRedirects(response, f'{reverse("channels.types.twilio.connect")}?claim_type=twilio_whatsapp')

        with patch("temba.tests.twilio.MockTwilioClient.MockAccounts.get") as mock_get:
            mock_get.return_value = MockTwilioClient.MockAccount("Trial")

            response = self.client.get(claim_twilio)
            self.assertIn("account_trial", response.context)
            self.assertTrue(response.context["account_trial"])

        with patch("temba.tests.twilio.MockTwilioClient.MockPhoneNumbers.list") as mock_search:
            search_url = reverse("channels.types.twilio.search")

            # try making empty request
            response = self.client.post(search_url, {})
            self.assertEqual(response.json(), [])

            # try searching for US number
            mock_search.return_value = [MockTwilioClient.MockPhoneNumber("+12062345678")]
            response = self.client.post(search_url, {"country": "US", "pattern": "206"})
            self.assertEqual(response.json(), ["+1 206-234-5678", "+1 206-234-5678", "+1 206-234-5678"])

            # try searching without area code
            response = self.client.post(search_url, {"country": "US", "pattern": ""})
            self.assertEqual(response.json(), ["+1 206-234-5678", "+1 206-234-5678", "+1 206-234-5678"])

            mock_search.return_value = []
            response = self.client.post(search_url, {"country": "US", "pattern": ""})
            self.assertEqual(
                response.json()["error"], "Sorry, no numbers found, please enter another area code and try again."
            )

            # try searching for non-US number
            mock_search.return_value = [MockTwilioClient.MockPhoneNumber("+442812345678")]
            response = self.client.post(search_url, {"country": "GB", "pattern": "028"})
            self.assertEqual(response.json(), ["+44 28 1234 5678", "+44 28 1234 5678", "+44 28 1234 5678"])

            mock_search.return_value = []
            response = self.client.post(search_url, {"country": "GB", "pattern": ""})
            self.assertEqual(
                response.json()["error"], "Sorry, no numbers found, please enter another pattern and try again."
            )

        with patch("temba.tests.twilio.MockTwilioClient.MockPhoneNumbers.stream") as mock_numbers:
            mock_numbers.return_value = iter([MockTwilioClient.MockPhoneNumber("+12062345678")])

            response = self.client.get(claim_twilio)
            self.assertContains(response, "206-234-5678")

            # claim it
            response = self.client.post(claim_twilio, dict(country="US", phone_number="12062345678"))
            self.assertFormError(
                response.context["form"], "phone_number", "Only existing Twilio WhatsApp number are supported"
            )

        with patch("temba.tests.twilio.MockTwilioClient.MockPhoneNumbers.stream") as mock_numbers:
            mock_numbers.return_value = iter([MockTwilioClient.MockPhoneNumber("+12062345678")])

            with patch("temba.tests.twilio.MockTwilioClient.MockPhoneNumbers.get") as mock_numbers_get:
                mock_numbers_get.return_value = MockTwilioClient.MockPhoneNumber("+12062345678")

                response = self.client.get(claim_twilio)
                self.assertContains(response, "206-234-5678")

                # claim it
                mock_numbers.return_value = iter([MockTwilioClient.MockPhoneNumber("+12062345678")])
                response = self.client.post(claim_twilio, dict(country="US", phone_number="+12062345678"))
                self.assertRedirects(response, reverse("public.public_welcome") + "?success")

                # make sure it is actually connected
                channel = Channel.objects.get(channel_type="TWA", org=self.org)
                self.assertEqual(channel.role, Channel.ROLE_SEND + Channel.ROLE_RECEIVE)

                # no more credential in the session
                self.assertNotIn(TwilioWhatsappType.SESSION_ACCOUNT_SID, self.client.session)
                self.assertNotIn(TwilioWhatsappType.SESSION_AUTH_TOKEN, self.client.session)

        twilio_channel = self.org.channels.all().first()
        # make channel support both sms and voice to check we clear both applications
        twilio_channel.role = Channel.ROLE_SEND + Channel.ROLE_RECEIVE + Channel.ROLE_ANSWER + Channel.ROLE_CALL
        twilio_channel.save()
        self.assertEqual("TWA", twilio_channel.channel_type)

        self.client.post(reverse("channels.channel_delete", args=[twilio_channel.pk]))
        self.assertIsNotNone(self.org.channels.all().first())

    def test_get_error_ref_url(self):
        self.assertEqual(
            "https://www.twilio.com/docs/api/errors/30006", TwilioWhatsappType().get_error_ref_url(None, "30006")
        )

    @patch("temba.channels.types.twilio.views.TwilioClient", MockTwilioClient)
    @patch("temba.channels.types.twilio.type.TwilioClient", MockTwilioClient)
    @patch("twilio.request_validator.RequestValidator", MockRequestValidator)
    def test_update(self):
        config = {
            Channel.CONFIG_ACCOUNT_SID: "TEST_SID",
            Channel.CONFIG_AUTH_TOKEN: "TEST_TOKEN",
        }
        twilio_whatsapp = self.org.channels.all().first()
        twilio_whatsapp.config = config
        twilio_whatsapp.channel_type = "TWA"
        twilio_whatsapp.save()

        update_url = reverse("channels.channel_update", args=[twilio_whatsapp.id])

        self.login(self.admin)
        response = self.client.get(update_url)
        self.assertEqual(
            ["name", "allow_international", "account_sid", "auth_token", "loc"],
            list(response.context["form"].fields.keys()),
        )

        post_data = dict(name="Foo channel", allow_international=False, account_sid="ACC_SID", auth_token="ACC_Token")

        response = self.client.post(update_url, post_data)

        self.assertEqual(response.status_code, 302)

        twilio_whatsapp.refresh_from_db()
        self.assertEqual(twilio_whatsapp.name, "Foo channel")
        # we used the primary credentials returned on the account fetch even though we submit the others
        self.assertEqual(twilio_whatsapp.config[Channel.CONFIG_ACCOUNT_SID], "AccountSid")
        self.assertEqual(twilio_whatsapp.config[Channel.CONFIG_AUTH_TOKEN], "AccountToken")
        self.assertTrue(twilio_whatsapp.check_credentials())

        with patch(
            "temba.channels.types.twilio_whatsapp.type.TwilioWhatsappType.check_credentials"
        ) as mock_check_credentials:
            mock_check_credentials.return_value = False

            response = self.client.post(update_url, post_data)
            self.assertFormError(response.context["form"], None, "Credentials don't appear to be valid.")

    @patch("requests.get")
    def test_fetch_templates(self, mock_get):
        config = {
            Channel.CONFIG_ACCOUNT_SID: "TEST_SID",
            Channel.CONFIG_AUTH_TOKEN: "TEST_TOKEN",
        }
        channel = self.org.channels.all().first()
        channel.config = config
        channel.channel_type = "TWA"
        channel.save()

        mock_get.side_effect = [
            RequestException("Network is unreachable", response=MockResponse(100, "")),
            MockResponse(400, '{ "meta": { "success": false } }'),
            MockResponse(
                200,
                json.dumps(
                    {
                        "contents": [
                            {
                                "friendly_name": "call_to_action_template",
                                "language": "en",
                                "links": {
                                    "approval_fetch": "https://content.twilio.com/v1/Content/HX1234500/ApprovalRequests"
                                },
                                "sid": "HX1234500",
                                "types": {
                                    "twilio/call-to-action": {
                                        "actions": [
                                            {"phone": "+12538678447", "title": "Call us", "type": "PHONE_NUMBER"},
                                            {
                                                "title": "Check site",
                                                "type": "URL",
                                                "url": "https://example.com/?wa_customer={{3}}",
                                            },
                                        ],
                                        "body": "Call to action {{1}} and {{2}}",
                                    }
                                },
                                "url": "https://content.twilio.com/v1/Content/HX1234500",
                                "variables": {"1": "for Product A", "2": "features A,B,C", "3": "id123"},
                            },
                            {
                                "friendly_name": "media_template",
                                "language": "en",
                                "links": {
                                    "approval_fetch": "https://content.twilio.com/v1/Content/HX1234501/ApprovalRequests"
                                },
                                "sid": "HX1234501",
                                "types": {
                                    "twilio/media": {
                                        "body": "Template with media for {{2}} can have a link with variables",
                                        "media": ["https://example.com/images/{{1}}.jpg"],
                                    },
                                },
                                "url": "https://content.twilio.com/v1/Content/HX1234501",
                                "variables": {"1": "for Product A", "2": "features A,B,C", "3": "id123"},
                            },
                            {
                                "friendly_name": "text_only_template",
                                "language": "en",
                                "links": {
                                    "approval_fetch": "https://content.twilio.com/v1/Content/HX1234502/ApprovalRequests"
                                },
                                "sid": "HX1234502",
                                "types": {
                                    "twilio/text": {
                                        "body": "Hello {{1}}, this is text example only and can have variables replaces such as {{2}} and {{3}}"
                                    },
                                    "url": "https://content.twilio.com/v1/Content/HX1234502",
                                    "variables": {"1": "for Product A", "2": "features A,B,C", "3": "id123"},
                                },
                            },
                        ],
                        "meta": {"next_page_url": "https://content.twilio.com/v1/Content?PageSize=50&Page=1"},
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps(
                    {
                        "contents": [
                            {
                                "friendly_name": "quick_reply_template",
                                "language": "en",
                                "links": {
                                    "approval_fetch": "https://content.twilio.com/v1/Content/HX1234503/ApprovalRequests"
                                },
                                "sid": "HX1234503",
                                "types": {
                                    "twilio/quick-reply": {
                                        "actions": [
                                            {"id": "subscribe", "title": "Subscribe {{2}}"},
                                            {"id": "stop", "title": "Stop promotions"},
                                            {"id": "help", "title": "Help for {{3}}"},
                                        ],
                                        "body": "Up to 3 buttons for quick replies here we can have variables in the body {{1}} and 20 character max for each button",
                                    }
                                },
                                "url": "https://content.twilio.com/v1/Content/HX1234503",
                                "variables": {"1": "Product A", "2": "Product B", "3": "Product C"},
                            }
                        ],
                        "meta": {"next_page_url": None},
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps(
                    {
                        "whatsapp": {
                            "category": "marketing",
                            "status": "approved",
                        }
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps(
                    {
                        "whatsapp": {
                            "category": "marketing",
                            "status": "approved",
                        }
                    }
                ),
            ),
            MockResponse(
                200,
                json.dumps(
                    {
                        "whatsapp": {
                            "category": "marketing",
                            "status": "rejected",
                        }
                    }
                ),
            ),
            MockResponse(400, "Error"),
        ]

        with self.assertRaises(RequestException):
            channel.type.fetch_templates(channel)

        self.assertEqual(1, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=True).count())

        with self.assertRaises(RequestException):
            channel.type.fetch_templates(channel)

        self.assertEqual(2, HTTPLog.objects.filter(log_type=HTTPLog.WHATSAPP_TEMPLATES_SYNCED, is_error=True).count())

        templates = channel.type.fetch_templates(channel)

        self.assertEqual(
            [
                {
                    "category": "marketing",
                    "components": [
                        {"text": "Call to action {{1}} and {{2}}", "type": "body"},
                        {
                            "buttons": [
                                {"phone_number": "+12538678447", "text": "Call us", "type": "PHONE_NUMBER"},
                                {"text": "Check site", "type": "URL", "url": "https://example.com/?wa_customer={{3}}"},
                            ],
                            "type": "buttons",
                        },
                    ],
                    "id": "HX1234500",
                    "language": "en",
                    "name": "call_to_action_template",
                    "status": "approved",
                },
                {
                    "category": "marketing",
                    "components": [
                        {"text": "Template with media for {{2}} can have a link with " "variables", "type": "body"},
                        {"format": "unknown", "type": "header"},
                    ],
                    "id": "HX1234501",
                    "language": "en",
                    "name": "media_template",
                    "status": "approved",
                },
                {
                    "category": "marketing",
                    "components": [
                        {
                            "text": "Hello {{1}}, this is text example only and can have "
                            "variables replaces such as {{2}} and {{3}}",
                            "type": "body",
                        }
                    ],
                    "id": "HX1234502",
                    "language": "en",
                    "name": "text_only_template",
                    "status": "rejected",
                },
                {
                    "category": "",
                    "components": [
                        {
                            "text": "Up to 3 buttons for quick replies here we can have "
                            "variables in the body {{1}} and 20 character max "
                            "for each button",
                            "type": "body",
                        },
                        {
                            "buttons": [
                                {"text": "Subscribe {{2}}", "type": "quick_reply"},
                                {"text": "Stop promotions", "type": "quick_reply"},
                                {"text": "Help for {{3}}", "type": "quick_reply"},
                            ],
                            "type": "buttons",
                        },
                    ],
                    "id": "HX1234503",
                    "language": "en",
                    "name": "quick_reply_template",
                    "status": "unsubmitted",
                },
            ],
            templates,
        )
