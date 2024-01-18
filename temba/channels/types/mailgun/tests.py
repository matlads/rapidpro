from django.urls import reverse

from temba.tests import TembaTest

from ...models import Channel


class MailgunTypeTest(TembaTest):
    def test_claim(self):
        claim_url = reverse("channels.types.mailgun.claim")

        self.login(self.admin)

        response = self.client.get(reverse("channels.channel_claim"))
        self.assertNotContains(response, claim_url)

        self.login(self.customer_support, choose_org=self.org)

        response = self.client.get(reverse("channels.channel_claim"))
        self.assertContains(response, claim_url)

        response = self.client.get(claim_url)
        self.assertEqual(200, response.status_code)

        response = self.client.post(claim_url, {"address": "acme.com", "sending_key": "0123456789"}, follow=True)
        self.assertEqual(200, response.status_code)

        channel = Channel.objects.get(channel_type="MLG")
        self.assertEqual("Mailgun: acme.com", channel.name)
        self.assertEqual("acme.com", channel.address)
        self.assertEqual({"auth_token": "0123456789"}, channel.config)
