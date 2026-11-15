"""Keycloak AsciiDoc link adapter.

Keycloak's generated documentation carries its own header links ("Edit this
section", "Report an issue", links to neighbouring guides). This adapter turns
them into the neutral Publisher link markers so that edit, issue and navigation
links can be routed independently. It is optional: projects whose documentation
build emits the neutral markers directly do not need it.
"""
from __future__ import annotations

import re
from html import escape, unescape
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from ..links import LinkResolutionError, _is_documentation_page_url, _prefix_suffix, _safe_relpath

NAME = "keycloak_asciidoc"


def validate_component(component: dict[str, Any], source_config: dict[str, Any]) -> str | None:
    """Return a configuration error message, or None when the component is valid."""
    if not source_config.get("vcs", {}).get("web_url"):
        return (
            f"Component {component['id']}: keycloak_asciidoc requires an explicit sources[].vcs.web_url "
            "separate from the authoring target"
        )
    return None


def adapt_page(
    page_text: str, *, config: dict[str, Any], component: dict[str, Any], edit: dict[str, Any],
    targets: dict[str, Any], link_policies: dict[str, dict[str, Any]], communication_channels: set[str],
    page_rel: str,
) -> str:
    """Return the page with Keycloak's native links replaced by Publisher markers.

    Raises LinkResolutionError when the page cannot be adapted safely.
    """
    source_id = component["source_id"]
    target = targets.get(edit.get("target_id"))
    if edit.get("mode", "inherit") == "override" and not target:
        raise LinkResolutionError("Keycloak AsciiDoc adapter requires a configured edit target_id")
    if target and target.get("source_id") not in (None, source_id):
        raise LinkResolutionError("Keycloak authoring target is configured for a different source_id")
    source_config = next((item for item in config.get("sources", []) if item.get("id") == source_id), None)
    source_vcs = (source_config or {}).get("vcs", {})
    try:
        transformed, _counts = transform_keycloak_asciidoc_edit_links(
            page_text, source_vcs, source_id,
            link_policies=link_policies,
            communication_channels=communication_channels,
            page_rel=page_rel,
        )
    except LinkResolutionError as exc:
        raise LinkResolutionError(f"Keycloak AsciiDoc link adaptation failed: {exc}") from exc
    return transformed


def transform_keycloak_asciidoc_edit_links(
    html_text: str, source: dict[str, Any], source_id: str,
    link_policies: dict[str, dict[str, Any]] | None = None,
    communication_channels: set[str] | None = None,
    page_rel: str = "",
) -> tuple[str, dict[str, int]]:
    """Attach source provenance to Keycloak edit links without choosing the editor target.

    The upstream HTML identifies its *source* repository and ref in the href:
    ``/<org>/<repo>/tree/<ref>/docs/documentation/<include_filename>``. Those
    values must be checked against the configured source identity, not against
    the separately configured authoring target. The normal marker resolver then
    maps the source-relative path to any explicitly configured authoring repo.
    Edit links are marked with exact source-file provenance. Issue links and
    explicitly configured neighboring-document URL prefixes receive distinct
    markers and can therefore be routed to independent destinations.
    """
    web = urlparse(str(source.get("web_url", "")))
    if web.scheme != "https" or (web.hostname or "").lower() != "github.com" or web.query or web.fragment:
        raise LinkResolutionError("Keycloak AsciiDoc adapter requires sources[].vcs.web_url to be an HTTPS GitHub repository URL")
    repo_path = web.path.strip("/")
    if not repo_path or len(repo_path.split("/")) != 2 or ".." in repo_path.split("/"):
        raise LinkResolutionError("Keycloak source web_url must identify exactly one GitHub owner/repository")
    ref = str(source.get("default_ref", ""))
    if not ref or "/" in ref or ref in {".", ".."}:
        raise LinkResolutionError("Keycloak AsciiDoc adapter requires a single-segment configured source ref")
    expected_prefixes = (
        f"/{repo_path}/edit/{ref}/docs/documentation/",
        f"/{repo_path}/tree/{ref}/docs/documentation/",
    )

    anchor_re = re.compile(r"<a\b(?P<attrs>[^>]*)>(?P<body>.*?)</a\s*>", re.IGNORECASE | re.DOTALL)
    href_re = re.compile(r"\bhref\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
    policies = link_policies or {}
    communication_channels = communication_channels or set()
    counts = {"edit": 0, "issues": 0, "navigation": 0}
    source_repo = urlparse(str(source.get("web_url", "")))
    source_issue_prefix = source_repo.path.rstrip("/") + "/issues/"
    issue_policy = policies.get("issues", {})
    navigation_policy = policies.get("navigation", {})

    def replace_anchor(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        body = match.group("body")
        label = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]*>", "", body))).strip().casefold()
        href_match = href_re.search(attrs)
        if not href_match:
            if label in {"edit this section", "edit this page"}:
                raise LinkResolutionError("Keycloak edit link has no href attribute")
            return match.group(0)
        href = unescape(href_match.group(2))
        parsed = urlparse(href)
        marker = ""
        marker_extra = ""

        if label in {"edit this section", "edit this page"}:
            matched_prefix = next(
                (prefix for prefix in expected_prefixes if parsed.path.startswith(prefix)), None
            )
            if (parsed.scheme != "https" or parsed.netloc.casefold() != "github.com"
                    or parsed.query or parsed.fragment or matched_prefix is None):
                raise LinkResolutionError(
                    "Keycloak edit link does not point to the configured source repository/ref "
                    "documentation edit or tree URL"
                )
            relative = unquote(parsed.path[len(matched_prefix):])
            source_file = _safe_relpath(f"docs/documentation/{relative}")
            if not source_file.lower().endswith(".adoc"):
                raise LinkResolutionError(f"Keycloak edit link does not identify an AsciiDoc source file: {source_file}")
            marker = "edit"
            marker_extra = (
                f' data-source-id="{escape(source_id, quote=True)}"'
                f' data-source-file="{escape(source_file, quote=True)}"'
            )
        else:
            # In override/disable mode the configured URL selectors define the
            # complete issue-link class. Do not depend on visible anchor text:
            # themes may rename the link, add icons, or localize its label.
            configured_issue_prefixes = issue_policy.get("source_prefixes", [])
            matches_configured_issue = (
                "issues" in policies
                and bool(configured_issue_prefixes)
                and _prefix_suffix(href, configured_issue_prefixes) is not None
            )
            label_is_issue = label in {"report an issue", "report issue"}
            matches_legacy_communication_issue = (
                label_is_issue and not configured_issue_prefixes
                and "issues" in communication_channels and "issues" not in policies
                and parsed.scheme == "https"
                and (parsed.hostname or "").lower() == (source_repo.hostname or "").lower()
                and parsed.path.startswith(source_issue_prefix)
            )
            if matches_configured_issue or matches_legacy_communication_issue:
                marker = "issues"
            else:
                navigation_prefixes = navigation_policy.get("source_prefixes", [])
                relative_prefixes = navigation_policy.get("relative_prefixes", [])
                routed_href = href
                is_selected_absolute_or_root = bool(
                    navigation_prefixes
                    and _prefix_suffix(href, navigation_prefixes) is not None
                    and _is_documentation_page_url(href)
                )
                is_selected_relative = bool(relative_prefixes) and any(
                    href.startswith(prefix) for prefix in relative_prefixes
                )
                if not is_selected_absolute_or_root and is_selected_relative:
                    source_page_base = navigation_policy.get("source_page_base_url", "")
                    if not source_page_base or not page_rel:
                        raise LinkResolutionError(
                            "Relative neighbor link selectors require links.navigation.source_page_base_url "
                            "and a component-relative page path"
                        )
                    current_source_page = urljoin(source_page_base.rstrip("/") + "/", page_rel)
                    routed_href = urljoin(current_source_page, href)
                    # A fragment or path that resolves back to the same page is not a neighbor page.
                    current_parsed = urlparse(current_source_page)
                    routed_parsed = urlparse(routed_href)
                    is_selected_absolute_or_root = (
                        routed_parsed.path != current_parsed.path
                        and navigation_prefixes
                        and _prefix_suffix(routed_href, navigation_prefixes) is not None
                        and _is_documentation_page_url(routed_href)
                    )
                if is_selected_absolute_or_root:
                    marker = "navigation"
                    href = routed_href

        if not marker:
            return match.group(0)
        cleaned = re.sub(
            r"\s+data-(?:publisher-link|source-id|source-file|original-href)\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
            "", attrs, flags=re.IGNORECASE,
        )
        marker_attrs = (
            f' data-publisher-link="{marker}"'
            f' data-original-href="{escape(href, quote=True)}"'
            + marker_extra
        )
        counts[marker] += 1
        return f"<a{cleaned}{marker_attrs}>{body}</a>"

    transformed = anchor_re.sub(replace_anchor, html_text)
    return transformed, counts
