import requests
from smartmin.views import SmartFormView, SmartModelActionView

from django import forms
from django.conf import settings
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from temba.orgs.views import ModalMixin, OrgObjPermsMixin

from ...models import Channel
from ...views import ClaimViewMixin


class ClaimView(ClaimViewMixin, SmartFormView):
    class Form(ClaimViewMixin.Form):
        user_access_token = forms.CharField(min_length=32, required=True, help_text=_("The User Access Token"))
        fb_user_id = forms.CharField(
            required=True, help_text=_("The Facebook User ID of the admin that connected the channel")
        )
        page_name = forms.CharField(required=True, help_text=_("The name of the Facebook page"))
        page_id = forms.IntegerField(required=True, help_text="The Facebook Page ID")

    form_class = Form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["claim_url"] = reverse("channels.types.facebookapp.claim")
        context["facebook_app_id"] = settings.FACEBOOK_APPLICATION_ID
        return context

    def form_valid(self, form):
        org = self.request.user.get_org()
        auth_token = form.cleaned_data["user_access_token"]
        name = form.cleaned_data["page_name"]
        page_id = form.cleaned_data["page_id"]
        fb_user_id = form.cleaned_data["fb_user_id"]

        app_id = settings.FACEBOOK_APPLICATION_ID
        app_secret = settings.FACEBOOK_APPLICATION_SECRET

        # get user long lived access token
        url = "https://graph.facebook.com/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": auth_token,
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:  # pragma: no cover
            raise Exception(_("Failed to get a user long lived token"))

        long_lived_auth_token = response.json().get("access_token", "")

        if long_lived_auth_token == "":  # pragma: no cover
            raise Exception(_("Empty user access token!"))

        url = f"https://graph.facebook.com/v7.0/{fb_user_id}/accounts"
        params = {"access_token": long_lived_auth_token}

        response = requests.get(url, params=params)

        if response.status_code != 200:  # pragma: no cover
            raise Exception(_("Failed to get a page long lived token"))

        response_json = response.json()

        page_access_token = ""
        for elt in response_json["data"]:
            if elt["id"] == str(page_id):
                page_access_token = elt["access_token"]
                name = elt["name"]
                break

        if page_access_token == "":  # pragma: no cover
            raise Exception(_("Empty page access token!"))

        config = {
            Channel.CONFIG_AUTH_TOKEN: page_access_token,
            Channel.CONFIG_PAGE_NAME: name,
        }
        self.object = Channel.create(
            org, self.request.user, None, self.channel_type, name=name, address=page_id, config=config
        )

        return super().form_valid(form)


class RefreshToken(ModalMixin, OrgObjPermsMixin, SmartModelActionView):
    class Form(forms.Form):
        user_access_token = forms.CharField(min_length=32, required=True, help_text=_("The User Access Token"))
        fb_user_id = forms.CharField(
            required=True, help_text=_("The Facebook User ID of the admin that connected the channel")
        )

    slug_url_kwarg = "uuid"
    success_url = "uuid@channels.channel_read"
    form_class = Form
    permission = "channels.channel_claim"
    fields = ()
    template_name = "channels/types/facebookapp/refresh_token.html"
    title = _("Reconnect Facebook Page")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["refresh_url"] = reverse("channels.types.facebookapp.refresh_token", args=(self.object.uuid,))
        context["facebook_app_id"] = settings.FACEBOOK_APPLICATION_ID

        resp = requests.get(
            "https://graph.facebook.com/v7.0/me",
            params={"access_token": self.object.config[Channel.CONFIG_AUTH_TOKEN]},
        )

        error_connect = False
        if resp.status_code != 200:
            error_connect = True

        context["error_connect"] = error_connect

        return context

    def get_queryset(self):
        return Channel.objects.filter(is_active=True, org=self.request.user.get_org(), channel_type="FBA")

    def execute_action(self):

        form = self.form
        channel = self.object

        auth_token = form.data["user_access_token"]
        fb_user_id = form.data["fb_user_id"]

        page_id = channel.address

        app_id = settings.FACEBOOK_APPLICATION_ID
        app_secret = settings.FACEBOOK_APPLICATION_SECRET

        # get user long lived access token
        url = "https://graph.facebook.com/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": auth_token,
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:  # pragma: no cover
            raise Exception(_("Failed to get a user long lived token"))

        long_lived_auth_token = response.json().get("access_token", "")

        if long_lived_auth_token == "":  # pragma: no cover
            raise Exception(_("Empty user access token!"))

        url = f"https://graph.facebook.com/v7.0/{fb_user_id}/accounts"
        params = {"access_token": long_lived_auth_token}

        response = requests.get(url, params=params)

        if response.status_code != 200:  # pragma: no cover
            raise Exception(_("Failed to get a page long lived token"))

        response_json = response.json()

        page_access_token = ""
        for elt in response_json["data"]:
            if elt["id"] == str(page_id):
                page_access_token = elt["access_token"]
                name = elt["name"]
                break

        if page_access_token == "":  # pragma: no cover
            raise Exception(_("Empty page access token!"))

        channel.config[Channel.CONFIG_AUTH_TOKEN] = page_access_token
        channel.config[Channel.CONFIG_PAGE_NAME] = name
        channel.save(update_fields=["config"])
