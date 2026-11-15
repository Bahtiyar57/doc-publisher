# Usage

Every page ends with two links that the Publisher rewrites after the build:

- **Edit this page** points to the repository where authors edit the file.
- **Report an issue** points to the configured issue tracker.

Both links are produced by `hooks/publisher_markers.py`. The Publisher removes
the markers from the final site.
