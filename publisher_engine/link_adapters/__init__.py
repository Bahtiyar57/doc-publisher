"""Source-specific link adapters.

An adapter translates the native link markup of one documentation toolchain into
the neutral Publisher link markers (see docs/LINKS-AND-COMMUNICATION.md). It is
selected per component with ``components[].link_adapter``.

An adapter module provides:

* ``NAME``: the identifier used in the configuration.
* ``validate_component(component, source_config)``: return an error message for
  an invalid component configuration, otherwise None.
* ``adapt_page(page_text, *, config, component, edit, targets, link_policies,
  communication_channels, page_rel)``: return the adapted HTML or raise
  ``LinkResolutionError``.

To add an adapter, create a module here, register it below and add its name to
the ``link_adapter`` enum in the configuration schema (both copies) and to
``data/provider-capabilities.json``.
"""
from __future__ import annotations

from types import ModuleType

from . import keycloak_asciidoc

ADAPTERS: dict[str, ModuleType] = {
    keycloak_asciidoc.NAME: keycloak_asciidoc,
}


def get_adapter(name: str) -> ModuleType | None:
    return ADAPTERS.get(name)
