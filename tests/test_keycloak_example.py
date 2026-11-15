"""Tests of the Keycloak reference example (examples/keycloak).

The engine does not depend on this example: when the directory is absent these
tests are skipped and the rest of the suite is unaffected.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from publisher_engine.config import load_config
from publisher_engine.engine import _rewrite_links
from publisher_engine.workflow import generate_github_actions_workflow, generate_github_source_notifier

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "keycloak"
NOTIFIER = EXAMPLE / "source-repository" / ".github" / "workflows" / "notify-documentation-publisher.yml"


@unittest.skipUnless(EXAMPLE.is_dir(), "Keycloak example is not present in this checkout")
class KeycloakExampleTests(unittest.TestCase):
    def test_keycloak_configuration_is_named_and_marked_as_smoke_only(self):
        smoke_path = EXAMPLE / "publisher.smoke.yml"
        self.assertTrue(smoke_path.is_file())
        self.assertFalse((EXAMPLE / "publisher.keycloak.example.yml").exists())
        text = smoke_path.read_text(encoding="utf-8")
        self.assertIn("NOT A GENERIC OR LIVE DEPLOYMENT CONFIGURATION", text)
        self.assertIn("publishing.dry_run: true", text)
        loaded = load_config(smoke_path)
        self.assertTrue(loaded["publishing"].get("dry_run", True))
        self.assertTrue(loaded["site"]["base_url"].endswith("example.invalid"))

    def test_keycloak_example_inherits_official_navigation_destinations(self):
        """The Keycloak example must not rewrite documentation navigation to the fork."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source"
            source_file = source / "docs/documentation/server_admin/index.adoc"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("= Keycloak Server Administration", encoding="utf-8")

            staging = root / "staging"
            page = staging / "docs/current/keycloak/server_admin/index.html"
            page.parent.mkdir(parents=True)
            official_links = [
                ("Getting Started", "https://www.keycloak.org/guides#getting-started"),
                ("Securing applications", "https://www.keycloak.org/guides#securing-apps"),
                ("Server Developer", "https://www.keycloak.org/docs/latest/server_development/index.html"),
                ("Authorization Services", "https://www.keycloak.org/docs/latest/authorization_services/index.html"),
                ("Upgrading", "https://www.keycloak.org/docs/latest/upgrading/index.html"),
                ("Release Notes", "https://www.keycloak.org/docs/latest/release_notes/index.html"),
            ]
            anchors = [
                f'<a href="{href}">{label}</a>' for label, href in official_links
            ]
            anchors.extend([
                '<a href="https://github.com/keycloak/keycloak/edit/main/docs/documentation/server_admin/index.adoc">Edit this section</a>',
                '<a href="https://github.com/keycloak/keycloak/issues/new?template=bug.yml&amp;title=Docs">Report an issue</a>',
            ])
            page.write_text('<html><body><nav>' + ''.join(anchors) + '</nav></body></html>', encoding="utf-8")

            # Load the actual example configuration instead of reconstructing its link policy in the test.
            config = load_config(EXAMPLE / "publisher.yml")
            navigation_policy = config.get("links", {}).get("navigation", {})
            self.assertEqual(navigation_policy, {"mode": "inherit"})
            errors, report = _rewrite_links(staging, config, config["components"], {"keycloak": source})

            self.assertEqual(errors, [])
            html = page.read_text(encoding="utf-8")
            for label, href in official_links:
                self.assertIn(f'href="{href}"', html, label)
                self.assertNotIn("github.com/devrimcode/keycloak/tree/main", html, label)
            self.assertIn(
                'href="https://github.com/devrimcode/keycloak/edit/main/docs/documentation/server_admin/index.adoc"',
                html,
            )
            self.assertIn(
                'href="https://github.com/keycloak/keycloak/issues/new?template=bug.yml&amp;title=Docs"',
                html,
            )
            self.assertFalse([item for item in report if item["channel"] == "navigation"])

    def test_production_config_keeps_source_edit_issue_and_inherited_navigation_contracts(self):
        cfg = load_config(EXAMPLE / "publisher.yml")
        source = next(item for item in cfg["sources"] if item["id"] == "keycloak")
        self.assertEqual(source["vcs"]["clone_url"], "https://github.com/devrimcode/keycloak.git")
        self.assertEqual(source["vcs"]["web_url"], "https://github.com/keycloak/keycloak")
        edit_target = next(item for item in cfg["authoring_targets"] if item["id"] == cfg["links"]["edit"]["target_id"])
        self.assertEqual(edit_target["repository"], "devrimcode/keycloak")
        self.assertEqual(cfg["links"]["issues"]["target_url"], "https://github.com/keycloak/keycloak")
        self.assertEqual(cfg["links"]["navigation"], {"mode": "inherit"})
        self.assertFalse(cfg["publishing"]["dry_run"])
        self.assertEqual(cfg["triggers"]["repository_dispatch"]["source_repository"], "devrimcode/keycloak")
        self.assertEqual(cfg["workflow"]["java_version"], "25")
        self.assertEqual(cfg["workflow"]["actions"]["setup_java"], "actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6")
        self.assertIn("-Daether.connector.http.retryHandler.count=5", cfg["workflow"]["environment"]["MAVEN_ARGS"])
        self.assertTrue(cfg["triggers"]["concurrency_group_per_ref"])
        self.assertFalse(cfg["triggers"]["cancel_in_progress"])

    def test_example_configurations_validate(self):
        for name in ("publisher.yml", "publisher.smoke.yml"):
            with self.subTest(config=name):
                self.assertIn("sources", load_config(EXAMPLE / name))

    def test_generated_workflow_expects_the_example_at_projects_keycloak(self):
        generated = generate_github_actions_workflow(load_config(EXAMPLE / "publisher.yml"))
        self.assertIn('CONFIG_FILE: "projects/keycloak/publisher.yml"', generated)
        self.assertIn('path: "projects/keycloak/_site"', generated)
        self.assertNotIn('CONFIG_FILE: "publisher.yml"', generated)

    def test_source_notifier_matches_generated_output(self):
        generated = generate_github_source_notifier(load_config(EXAMPLE / "publisher.yml"))
        self.assertEqual(NOTIFIER.read_text(encoding="utf-8"), generated)


if __name__ == "__main__":
    unittest.main()
