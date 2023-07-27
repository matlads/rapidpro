from smartmin.views import SmartFormView

from django import forms
from django.utils.translation import gettext_lazy as _

from ...models import Channel
from ...views import ClaimViewMixin

SUPPORTED_COUNTRIES = {
    "AU",  # Australia
    "AT",  # Austria
    "BE",  # Belgium
    "CA",  # Canada
    "CL",  # Chile
    "CZ",  # Czech Republic
    "DK",  # Denmark  # Beta
    "EE",  # Estonia
    "FI",  # Finland
    "FR",  # France  # Beta
    "DE",  # Germany
    "EE",  # Estonia
    "HK",  # Hong Kong
    "HU",  # Hungary  # Beta
    "IE",  # Ireland,
    "IL",  # Israel  # Beta
    "IT",  # Italy  # Beta
    "LT",  # Lithuania
    "MY",  # Malaysia
    "MX",  # Mexico  # Beta
    "NL",  # Netherlands
    "NO",  # Norway
    "PH",  # Philippines  # Beta
    "PL",  # Poland
    "PR",  # Puerto Rico
    "PT",  # Portugal
    "ES",  # Spain
    "SE",  # Sweden
    "SG",  # Singapore  # Beta
    "CH",  # Switzerland
    "GB",  # United Kingdom
    "US",  # United States
    "VI",  # Virgin Islands
    "VN",  # Vietnam  # Beta
    "ZA",  # South Africa  # Beta
}

class ClaimView(ClaimViewMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        title = forms.CharField(
            max_length=64,
            required=True,
            label=_("Messagebird Environment Title"),
            help_text=_("The name of your environment"),
        )

        signing_key = forms.CharField(
            required=True,
            label=_("Messagebird API Signing Key"),
            help_text=_(
                "Signing Key used to verify signatures. See https://developers.messagebird.com/api/#verifying-http-requests"
            ),
        )
        phone_num = forms.IntegerField(
            required=True,
            label=_("Originating Phone number"),
            help_text=_("The sending phone number or shortcode. Digits only"),
        )
        auth_token = forms.CharField(
            required=True,
            label=_("Messagebird API Auth Token"),
            help_text=_("The API auth token"),
        )

    form_class = Form

    def form_valid(self, form):
        title = form.cleaned_data.get("title")
        phone_num = form.cleaned_data.get("phone_num")
        auth_token = form.cleaned_data.get("auth_token")
        signing_key = form.cleaned_data.get("signing_key")
        config = {
            Channel.CONFIG_SECRET: signing_key,
            Channel.CONFIG_AUTH_TOKEN: auth_token,
        }

        self.object = Channel.create(
            self.request.org,
            self.request.user,
            None,
            self.channel_type,
            address=phone_num,
            name=title,
            config=config,
        )

        return super().form_valid(form)
