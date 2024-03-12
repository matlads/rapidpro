from temba.tests import TembaTest

from .models import Template, TemplateTranslation


class TemplateTest(TembaTest):
    def test_templates(self):
        tt1 = TemplateTranslation.get_or_create(
            self.channel,
            "hello",
            locale="eng-US",
            status=TemplateTranslation.STATUS_PENDING,
            external_id="1234",
            external_locale="en_US",
            namespace="",
            components={"body": {"content": "Hello {{1}}", "params": [{"type": "text"}]}},
            raw_components=[{"type": "BODY", "text": "Hello {{1}}"}],
            # deprecated
            content="Hello {{1}}",
            variable_count=1,
            params={"body": [{"type": "text"}]},
        )
        tt2 = TemplateTranslation.get_or_create(
            self.channel,
            "hello",
            locale="fra-FR",
            status=TemplateTranslation.STATUS_PENDING,
            external_id="5678",
            external_locale="fr_FR",
            namespace="",
            components={"body": {"content": "Bonjour {{1}}", "params": [{"type": "text"}]}},
            raw_components=[{"type": "BODY", "text": "Bonjour {{1}}"}],
            # deprecated
            content="Bonjour {{1}}",
            variable_count=1,
            params={"body": [{"type": "text"}]},
        )

        self.assertEqual(tt1.template, tt2.template)
        modified_on = tt1.template.modified_on

        tt3 = TemplateTranslation.get_or_create(
            self.channel,
            "hello",
            locale="fra-FR",
            status=TemplateTranslation.STATUS_PENDING,
            external_id="5678",
            external_locale="fr_FR",
            namespace="foo_namespace",
            components={"body": {"content": "Salut {{1}}", "params": [{"type": "text"}]}},
            raw_components=[{"type": "BODY", "text": "Salut {{1}}"}],
            # deprecated
            content="Salut {{1}}",
            variable_count=1,
            params={"body": [{"type": "text"}]},
        )

        self.assertTrue(tt3.template.modified_on > modified_on)
        self.assertEqual(tt3.namespace, "foo_namespace")
        self.assertEqual(1, Template.objects.filter(org=self.org).count())
        self.assertEqual(2, TemplateTranslation.objects.filter(channel=self.channel).count())

        # trim them
        TemplateTranslation.trim(self.channel, [tt1])

        # tt2 should be inactive now
        tt2.refresh_from_db()
        self.assertFalse(tt2.is_active)
