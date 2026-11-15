# Source-to-Publisher automatic deployment

This document describes the event contract that rebuilds a published site when its documentation repository changes. The repository roles stay independent: the Publisher reads the documentation repository and never writes to it. A concrete configuration is [`examples/keycloak/`](../examples/keycloak/README.md).

## Repository roles

- **Publisher repository:** contains the engine, the project configuration and the generated workflow, and serves the GitHub Pages site.
- **Documentation (source) repository:** contains the content and the build; the Publisher clones it and integrates it with `git subtree`.
- **Authoring target:** the repository where authors edit files. It may differ from the source repository.
- **Issue and navigation destinations:** configured independently of both.

Edit, issue and navigation destinations are independently configurable; changing the build clone does not change their routing policies.

## Configuration

The project configuration declares the event contract:

```yaml
sources:
  - id: <source-id>
    vcs:
      clone_url: https://github.com/<owner>/<repository>.git
      default_ref: <branch>
      dispatch_sha_env: PUBLISHER_SOURCE_SHA
triggers:
  repository_dispatch:
    event_type: <lower-case-event-type>
    source_id: <source-id>
    source_repository: <owner>/<repository>
    source_branch: <branch>
```

`source_repository` and `source_branch` must match the source's `clone_url` and `default_ref`. The Publisher passes the commit of the event to the build through the environment variable named by `dispatch_sha_env`.

## Event flow

1. A push to the configured branch of the documentation repository starts the source-side workflow, which `generate-source-notifier` creates from the project configuration.
2. That workflow sends a GitHub `repository_dispatch` event to the Publisher repository, with the configured event type and the payload fields `repository`, `ref` and the exact commit `sha`.
3. The Publisher workflow accepts only that event type. Before building, it verifies that the payload repository and ref are exactly the configured ones and that the SHA is a full 40- or 64-character Git commit ID.
4. `git_subtree` fetches and integrates that exact commit rather than a later moving branch head.
5. The build tasks, site assembly, URL rewriting, manifest generation and site validation run normally.
6. Before the Pages artifact upload, a repository-dispatch run compares the event SHA with the current head of the configured source branch. A delayed event for an older commit is marked stale and does not upload a Pages artifact.
7. The separate deploy job repeats the source-head check immediately before calling `deploy-pages`. If the branch has moved since the build completed, the deploy action is skipped and the existing Pages site remains in place.
8. Pages deployment still requires a successful build and site validation and the configured deploy branch. Pull requests never deploy.

Manual Publisher runs and normal pushes to the Publisher repository do not set the dispatch SHA variable; they fetch the configured branch of the source. Concurrency can be scoped by `github.ref`; with `concurrency_group_per_ref: true` and `cancel_in_progress: false`, a pull-request run cannot cancel a running deployment.

## Install the source-side workflow

Generate the workflow from the project configuration:

```sh
documentation-publisher generate-source-notifier --config projects/<name>/publisher.yml
```

It is written to `projects/<name>/source-repository/.github/workflows/notify-documentation-publisher.yml` unless `--output` is given. An existing file is only replaced with `--replace-existing`. Copy the file to `.github/workflows/notify-documentation-publisher.yml` in the documentation repository. It is kept below `projects/` so it is not accidentally installed into the Publisher repository's own workflows.

Create a fine-grained personal access token (or a GitHub App installation token) restricted to the single Publisher repository and grant the `Contents: write` repository permission required by GitHub's Create a repository dispatch event API. Store the token in the **documentation repository** as an Actions repository secret named:

`PUBLISHER_DISPATCH_TOKEN`

The source workflow itself receives only `contents: read`; it does not use the documentation repository's `GITHUB_TOKEN` for cross-repository writes. Do not put the dispatch token in YAML, commit it, or print it in logs. If the Publisher repository name or the event contract changes, regenerate the notifier.

The token is used only by the source workflow step that creates the event. The Publisher workflow does not receive it. Its own build permissions remain `contents: read`; its deploy job keeps only the configured Pages permissions. Because GitHub's repository-dispatch endpoint requires the receiving repository's `Contents: write` permission, the fine-grained token has more capability than the single dispatch call. Restrict it to the one Publisher repository, never expose it to pull-request workflows, protect the documentation repository's source branch, and require review for changes to the notifier workflow. A GitHub App installation token can be used instead when short-lived credentials are preferred; it still needs the receiving repository permission required by the endpoint.

## GitHub Actions prerequisites

- The generated Publisher workflow must be present on the Publisher repository's default branch. GitHub only runs `repository_dispatch` workflows when the workflow file exists on that default branch.
- The Publisher workflow must be enabled, and GitHub Pages must use **GitHub Actions** as its deployment source.
- The documentation repository must be publicly readable with `auth.mode: none`, or an explicit read-only source credential must be configured separately.
- The source-side workflow must be added to the documentation repository and the secret must be configured there. These remote setup steps are not performed by the Publisher.

## Fail-closed behavior and limitations

The Publisher rejects a dispatch with a wrong repository, wrong branch, missing or malformed SHA, or mismatched configured source. It never accepts an arbitrary ref from the event. The source commit actually integrated is recorded in `build-manifest.json` as `source_commit` and `source_revisions`.

If the build, link resolution, site validation, artifact upload, or Pages deployment fails, a new Pages artifact is not deployed. The previous public Pages deployment remains the last known published site. The source-head freshness checks prevent a delayed older dispatch from replacing a newer source revision, subject to the unavoidable interval between the final remote-head check and the deployment action. The next source push triggers its own build.

Both workflow sides can be generated and tested locally. A real cross-repository dispatch, GitHub Actions run and Pages deployment require the source workflow and secret to be configured in GitHub first. The generator supports GitHub only; the notifier requires a `publisher.clone_url` of the form `https://github.com/<owner>/<repository>.git`.
