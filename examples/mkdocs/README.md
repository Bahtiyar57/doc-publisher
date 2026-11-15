# Example: MkDocs

This example publishes a [MkDocs](https://www.mkdocs.org/) project with the Documentation Publisher. It contains nothing specific to Keycloak and shows what another project has to provide.

## What a project provides

| Concern | In this example |
|---|---|
| Source | A Git repository with `mkdocs.yml` and Markdown files (`source/` is a sample of it). |
| Build | `python -m mkdocs build --strict --site-dir build/site`, configured as a `command` task in `publisher.yml`. |
| Link markers | `source/hooks/publisher_markers.py` appends an *Edit this page* and a *Report an issue* link to every page. The Publisher rewrites them after the build. |
| Link targets | `authoring_targets` and `communication.issues` in `publisher.yml`. |

The marker contract is described in [docs/LINKS-AND-COMMUNICATION.md](../../docs/LINKS-AND-COMMUNICATION.md#link-marker-contract-for-documentation-builds).

## Using it for your own project

1. Copy `source/` into your documentation repository, or add `hooks/publisher_markers.py` and the `hooks:` entry to your existing `mkdocs.yml`.
2. Copy `publisher.yml`, replace every `example-org` URL, and check the paths in `mapping.source_prefix`/`target_prefix`.
3. Set `SITE_URL` in the build task to the final public URL of the component: `site.base_url` + `site.base_path` + `components_root/version/route`. `mkdocs.yml` reads it with `!ENV`. Without it MkDocs writes root-relative links into `404.html` that point outside the component, and the Publisher's site validation rejects the build.
4. Run `python -m publisher_engine.cli validate-config --config publisher.yml`.
5. To generate the Publisher workflow and the notifier for the documentation repository, follow steps 3 and 4 of [docs/ADDING-A-PROJECT.md](../../docs/ADDING-A-PROJECT.md). The test below runs exactly these commands against this example.

## Test

```bash
python -m pip install -r requirements-examples.txt
python -m pytest -q tests/test_example_mkdocs.py
```

The test clones two local Git repositories, runs the real MkDocs build through the engine and checks that the edit and issue links were rewritten and that no markers remain. It is skipped when MkDocs is not installed.
