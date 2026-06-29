"""
Backward-compatible entry point for Donovan VGA Planets crawls.

The implementation lives in :mod:`static_html_site_export`; this module only preserves
the historical script name and import path.
"""

from __future__ import annotations

from static_html_site_export import main

if __name__ == "__main__":
    main()
