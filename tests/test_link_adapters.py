"""Contract of the link adapter registry."""
from __future__ import annotations

import unittest

from publisher_engine import link_adapters


class LinkAdapterRegistryTests(unittest.TestCase):
    def test_every_registered_adapter_follows_the_adapter_contract(self):
        self.assertTrue(link_adapters.ADAPTERS)
        for name, adapter in link_adapters.ADAPTERS.items():
            with self.subTest(adapter=name):
                self.assertEqual(adapter.NAME, name)
                self.assertTrue(callable(adapter.validate_component))
                self.assertTrue(callable(adapter.adapt_page))
                self.assertIs(link_adapters.get_adapter(name), adapter)

    def test_unknown_adapter_is_not_resolved(self):
        self.assertIsNone(link_adapters.get_adapter("does_not_exist"))

    def test_registered_adapters_match_the_configuration_schema(self):
        import json
        from importlib import resources

        schema = json.loads(resources.files("publisher_engine").joinpath("data", "publisher.schema.json").read_text(encoding="utf-8"))
        enum = schema["$defs"]["component"]["properties"]["link_adapter"]["enum"]
        self.assertEqual(sorted(enum), sorted(link_adapters.ADAPTERS))

    def test_keycloak_adapter_requires_an_explicit_source_web_url(self):
        adapter = link_adapters.get_adapter("keycloak_asciidoc")
        self.assertIn("web_url", adapter.validate_component({"id": "docs"}, {"vcs": {}}))
        self.assertIsNone(adapter.validate_component({"id": "docs"}, {"vcs": {"web_url": "https://github.com/acme/docs"}}))


if __name__ == "__main__":
    unittest.main()
