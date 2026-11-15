"""MkDocs hook that emits Documentation Publisher link markers.

The Publisher rewrites anchors that carry a ``publisher-link-<channel>`` class:

* ``publisher-link-edit`` with ``href="publisher-source:<path>"`` becomes the
  configured edit URL for that source file.
* ``publisher-link-issues`` becomes the configured issue URL; the page title is
  passed through ``data-page-title``.

The source path must be relative to the root of the source repository. MkDocs is
run from that root, so the path is derived from the absolute source path.
"""
from __future__ import annotations

import os
from html import escape


def on_page_markdown(markdown, page, config, files):
    source_path = os.path.relpath(page.file.abs_src_path).replace(os.sep, "/")
    title = escape(page.title or page.file.src_uri, quote=True)
    footer = (
        '\n\n<p class="publisher-footer">'
        f'<a class="publisher-link-edit" href="publisher-source:{escape(source_path, quote=True)}">Edit this page</a> | '
        f'<a class="publisher-link-issues" data-page-title="{title}" href="#">Report an issue</a>'
        "</p>\n"
    )
    return markdown + footer
