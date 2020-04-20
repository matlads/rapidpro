from abc import ABCMeta
from uuid import uuid4

from smartmin.models import SmartModel

from django.conf.urls import url
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.template import Engine
from django.utils import timezone

from temba.contacts.models import Contact
from temba.orgs.models import Org


class TicketingServiceType(metaclass=ABCMeta):
    """
    TicketingServiceType is our abstract base type for ticketing services.
    """

    # the verbose name for this ticketing service type
    name = None

    # the short code for this ticketing service type (< 16 chars, lowercase)
    slug = None

    # the icon to show for this ticketing service type
    icon = "icon-channel-external"

    # the blurb to show on the main connect page
    connect_blurb = None

    # the view that handles connection of a new service
    connect_view = None

    def get_connect_blurb(self):
        """
        Gets the blurb for use on the connect page
        """
        return Engine.get_default().from_string(self.connect_blurb)

    def get_form_blurb(self):
        """
        Gets the blurb for use on the connect page
        """
        return Engine.get_default().from_string(self.form_blurb)

    def get_urls(self):
        """
        Returns all the URLs this ticketing service exposes to Django, the URL should be relative.
        """
        return [self.get_connect_url()]

    def get_connect_url(self):
        """
        Gets the URL/view configuration for this ticketing service's connect page
        """
        return url(r"^connect", self.connect_view.as_view(service_type=self), name="connect")


class TicketingService(SmartModel):
    """
    A ticketing service is a specific connection of a service, say Zendesk with an organization
    """

    # our uuid
    uuid = models.UUIDField(default=uuid4)

    # the type of this ticketing service
    service_type = models.CharField(max_length=16)

    # the org this ticketing service is connected to
    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="ticketing_services")

    # a name for this ticketing service
    name = models.CharField(max_length=64)

    # the configuration options for this ticketing service
    config = JSONField(null=True)

    @classmethod
    def create(cls, org, user, service_type, name, config):
        service = TicketingService.objects.create(
            uuid=uuid4(),
            service_type=service_type,
            name=name,
            config=config,
            org=org,
            created_by=user,
            modified_by=user,
            created_on=timezone.now(),
            modified_on=timezone.now(),
        )

        return service

    def get_type(self):
        """
        Returns the type instance for this ticketing service
        """
        from .types import TYPES

        return TYPES[self.service_type]

    def release(self):
        """
        Releases this ticketing service, closing all associated tickets in the process
        """
        # TODO: dependencies? or is ticketing a runtime thing?
        for ticket in self.tickets.all():
            ticket.close()

        self.is_active = False
        self.save(update_fields=["is_active", "modified_on"])

    @classmethod
    def get_types(cls):
        """
        Returns the possible types available for ticketing services
        """
        from .types import TYPES

        return TYPES.values()


class Ticket(models.Model):
    """
    A ticket represents a contact-initiated question or dialog.
    """

    STATUS_OPEN = "O"
    STATUS_CLOSED = "C"
    STATUS_EXPIRED = "X"

    # our uuid
    uuid = models.UUIDField(unique=True, default=uuid4)

    # the organization this ticket belongs to
    org = models.ForeignKey(Org, on_delete=models.PROTECT)

    # the ticketing service that this ticket belongs to
    service = models.ForeignKey(TicketingService, on_delete=models.PROTECT, related_name="tickets")

    # the contact this ticket is tied to
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT)

    # the subject of the ticket
    subject = models.TextField()

    # TODO: tickets should have a body as well

    # the external id of the ticket
    external_id = models.CharField(null=True, max_length=255)

    # any configuration attributes for this ticket
    config = JSONField(null=True)

    # the status of this ticket, one of open, closed, expired
    status = models.CharField(max_length=1)

    # when this ticket was opened
    opened_on = models.DateTimeField(default=timezone.now)

    # when this ticket was last modified
    modified_on = models.DateTimeField(null=True)

    # when this ticket was closed or expired
    # TODO: should this be something less close specific?
    closed_on = models.DateTimeField(null=True)

    def close(self):
        """
        Closes the ticket, un-pausing our contact in the process
        """
        self.status = Ticket.STATUS_CLOSED
        self.closed_on = timezone.now()
        self.save(update_fields=["status", "closed_on"])

        # TODO: should probably be a method on contact / mailroom
        self.contact.is_paused = False
        self.contact.save(update_fields=["is_paused", "modified_on"])
