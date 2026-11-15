"""The MkDocs example proves that the engine is not tied to Keycloak.

The build uses a real documentation tool (MkDocs) and the generic link markers.
The end-to-end test is skipped when MkDocs is not installed
(``pip install -r requirements-examples.txt``).
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "mkdocs"
HAS_MKDOCS = importlib.util.find_spec("mkdocs") is not None


def git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def make_remote(base: Path, name: str, source_dir: Path | None, files: dict[str, str] | None = None) -> Path:
    """Create a bare Git remote filled from a directory or a dict of files."""
    bare = base / f"{name}.git"
    work = base / f"{name}-work"
    git(["init", "--bare", str(bare)], base)
    if source_dir is not None:
        shutil.copytree(source_dir, work)
    else:
        work.mkdir()
    git(["init", "-b", "main", str(work)], base)
    git(["config", "user.name", "Fixture Author"], work)
    git(["config", "user.email", "fixture@example.invalid"], work)
    for rel, content in (files or {}).items():
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(["add", "."], work)
    git(["commit", "-m", "fixture"], work)
    git(["remote", "add", "origin", str(bare)], work)
    git(["push", "-u", "origin", "main"], work)
    return bare


class MkDocsExampleConfigTests(unittest.TestCase):
    def test_example_validates_as_shipped(self):
        result = subprocess.run(
            [sys.executable, "-m", "publisher_engine.cli", "validate-config", "--config", str(EXAMPLE / "publisher.yml")],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_example_uses_no_source_specific_link_adapter(self):
        config = yaml.safe_load((EXAMPLE / "publisher.yml").read_text(encoding="utf-8"))
        for component in config["components"]:
            self.assertNotIn("link_adapter", component)
        text = (EXAMPLE / "publisher.yml").read_text(encoding="utf-8")
        self.assertNotIn("devrimcode", text)


@unittest.skipUnless(HAS_MKDOCS, "MkDocs is not installed; run: pip install -r requirements-examples.txt")
class MkDocsExampleBuildTests(unittest.TestCase):
    def test_real_mkdocs_build_is_published_with_rewritten_links(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            publisher = make_remote(tmp, "publisher", None, {"README.md": "publisher\n"})
            source = make_remote(tmp, "mkdocs-sample", EXAMPLE / "source")

            config = yaml.safe_load((EXAMPLE / "publisher.yml").read_text(encoding="utf-8"))
            config["publisher"]["clone_url"] = str(publisher)
            config["publisher"].pop("allowed_hosts", None)
            source_vcs = config["sources"][0]["vcs"]
            source_vcs["clone_url"] = str(source)
            source_vcs.pop("allowed_hosts", None)
            config["build_tasks"][0]["argv"][0] = sys.executable
            config["workspace"]["temp_root"] = str(tmp / "runs")
            config_path = tmp / "example.yml"
            config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "publisher_engine.cli", "build", "--config", str(config_path),
                 "--components", "guide", "--replace-output"],
                cwd=tmp, env={**os.environ, "PYTHONPATH": str(ROOT)}, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            site = tmp / "_site"
            page = (site / "docs/current/guide/index.html").read_text(encoding="utf-8")
            usage = (site / "docs/current/guide/usage/index.html").read_text(encoding="utf-8")

            # Edit links point to the configured authoring repository, one per source file.
            self.assertIn('href="https://github.com/example-org/mkdocs-sample/edit/main/docs/index.md"', page)
            self.assertIn('href="https://github.com/example-org/mkdocs-sample/edit/main/docs/usage.md"', usage)
            # Issue links use the configured template and the page title.
            self.assertIn("https://github.com/example-org/mkdocs-sample/issues/new?title=", page)
            # No Publisher markers leak into the published site.
            for html in (page, usage):
                self.assertNotIn("publisher-link-", html)
                self.assertNotIn("publisher-source:", html)
            self.assertTrue((site / "build-manifest.json").is_file())


class MkDocsExampleAutomationTests(unittest.TestCase):
    """Steps 3 and 4 of docs/ADDING-A-PROJECT.md, applied to the example project."""

    def test_example_generates_publisher_workflow_and_source_notifier(self):
        sha = "a" * 40
        config = yaml.safe_load((EXAMPLE / "publisher.yml").read_text(encoding="utf-8"))
        config["sources"][0]["vcs"]["dispatch_sha_env"] = "PUBLISHER_SOURCE_SHA"
        config["publishing"]["dry_run"] = False  # explicit opt-in: the workflow uploads and deploys the Pages artifact
        config["triggers"] = {
            "manual": True, "push_branches": ["main"], "pull_request": True, "deploy_branch": "main",
            "repository_dispatch": {
                "event_type": "mkdocs-sample-updated", "source_id": "mkdocs-source",
                "source_repository": "example-org/mkdocs-sample", "source_branch": "main",
            },
        }
        config["workflow"] = {
            "provider": "github_actions", "file": ".github/workflows/documentation-publisher.yml",
            "config_file": "projects/mkdocs-example/publisher.yml", "python_version": "3.13",
            "actions": {
                "checkout": f"actions/checkout@{sha}", "setup_python": f"actions/setup-python@{sha}",
                "upload_pages_artifact": f"actions/upload-pages-artifact@{sha}", "deploy_pages": f"actions/deploy-pages@{sha}",
            },
        }
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            profile = tmp / "profiles" / "mkdocs-example"
            profile.mkdir(parents=True)
            config_path = profile / "publisher.yml"
            config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": str(ROOT)}
            outputs = {"generate-workflow": tmp / "workflow.yml", "generate-source-notifier": tmp / "notify.yml"}
            for command, output in outputs.items():
                result = subprocess.run(
                    [sys.executable, "-m", "publisher_engine.cli", command, "--config", str(config_path), "--output", str(output)],
                    cwd=tmp, env=env, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, command + "\n" + result.stdout + result.stderr)
            workflow = outputs["generate-workflow"].read_text(encoding="utf-8")
            self.assertIn('CONFIG_FILE: "projects/mkdocs-example/publisher.yml"', workflow)
            self.assertIn('path: "projects/mkdocs-example/_site"', workflow)
            self.assertIn("mkdocs-sample-updated", workflow)
            notifier = outputs["generate-source-notifier"].read_text(encoding="utf-8")
            self.assertIn('"example-org/mkdocs-sample"', notifier)
            self.assertIn('event_type:"mkdocs-sample-updated"', notifier)
            self.assertIn("repos/example-org/documentation-publisher/dispatches", notifier)
            self.assertNotIn("keycloak", (workflow + notifier).lower())


if __name__ == "__main__":
    unittest.main()
