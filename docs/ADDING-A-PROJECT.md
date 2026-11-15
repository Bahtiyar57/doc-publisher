# Adding a documentation project

The Publisher repository publishes; the documentation stays in its own repository. A project needs three things: a documentation build, a project directory `projects/<name>/`, and, optionally, a small generated workflow in the documentation repository that triggers a rebuild. The Publisher reads the documentation repository and never writes to it.

## 1. Prepare the documentation repository

- It needs a command that produces static HTML, for example `mkdocs build`, `sphinx-build`, `antora`, `npm run build` or `mvn`. The Publisher runs it as a plain `argv` array, never through a shell.
- For "Edit this page" and "Report an issue" links that point where you want, the build emits neutral link markers. They are described in [LINKS-AND-COMMUNICATION.md](LINKS-AND-COMMUNICATION.md#link-marker-contract-for-documentation-builds). [`examples/mkdocs/`](../examples/mkdocs/README.md) shows a complete setup with MkDocs. A build without markers can still be assembled, validated and published; only the link rewriting needs them.

## 2. Create the project directory

```sh
mkdir -p projects/<name>
documentation-publisher init-config --output projects/<name>/publisher.yml
```

Alternatively copy [`examples/mkdocs/publisher.yml`](../examples/mkdocs/publisher.yml) as a working start. Replace the placeholders: the Publisher repository, the documentation repository, the authoring target for edit links, the build task, the component and the public site URL and base path. Then check the result locally:

```sh
documentation-publisher validate-config --config projects/<name>/publisher.yml
documentation-publisher plan --config projects/<name>/publisher.yml
documentation-publisher build --config projects/<name>/publisher.yml --components all
```

Relative paths in a configuration are resolved from the directory of the file, so the site is built into `projects/<name>/_site`.

## 3. Generate the Publisher workflow

Add a `workflow:` section (provider, `file`, `config_file: projects/<name>/publisher.yml` and pinned action SHAs) and a `triggers:` section, see [CI-AND-PUBLISHING.md](CI-AND-PUBLISHING.md). Then, inside the Git checkout:

```sh
documentation-publisher generate-workflow --config projects/<name>/publisher.yml --replace-existing
```

The workflow reads the project's configuration and builds and validates the site. With `publishing.dry_run: false` in the configuration, which is the explicit deployment opt-in, it also uploads `projects/<name>/_site` and deploys it to GitHub Pages; the default `true` only builds. Live publishing rejects reserved example origins, so set a real `site.base_url`. Commit the workflow to the default branch and set **Settings > Pages > Source** to **GitHub Actions**.

## 4. Rebuild when the documentation changes (optional)

Add the dispatch contract to the project's configuration:

```yaml
sources:
  - id: handbook
    vcs:
      dispatch_sha_env: PUBLISHER_SOURCE_SHA   # in addition to the existing vcs fields
triggers:
  repository_dispatch:
    event_type: handbook-updated
    source_id: handbook
    source_repository: acme/handbook
    source_branch: main
```

Regenerate the Publisher workflow, then generate the workflow for the documentation repository:

```sh
documentation-publisher generate-source-notifier --config projects/<name>/publisher.yml
```

The file is written to `projects/<name>/source-repository/.github/workflows/notify-documentation-publisher.yml`. Copy it to the same path in the documentation repository and add the repository secret `PUBLISHER_DISPATCH_TOKEN` there. All values in the file come from the project's configuration. Token scope, event flow and the deploy checks are described in [SOURCE-TO-PUBLISHER-AUTOMATION.md](SOURCE-TO-PUBLISHER-AUTOMATION.md).

## Several projects

A GitHub repository serves one Pages site. Several documentation repositories can be sources and components of one project and are then published as one site. Separate sites need separate Publisher repositories. Each Publisher repository has one active workflow, generated from one project's configuration.

## Starting from the Keycloak example

[`examples/keycloak/`](../examples/keycloak/README.md) is a reference configuration for the Keycloak documentation. It is not active; copy it to `projects/keycloak/`, replace the repository names and generate the workflows as described there. Everything else in this repository, including the test suite, works without it, and its tests are skipped when the directory is missing.
