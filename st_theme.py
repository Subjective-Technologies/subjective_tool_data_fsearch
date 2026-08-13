"""subjectivetechnologies.com branding palette for standalone Qt tools.

Single source of truth is ``assets/themes/theme_subjectivetechnologies.json`` at
the repo root, itself derived from the web dashboard's Subjective branding
profile (``subjective-dashboard-theme.css`` / ``subjective-profile.css``).

This module is deliberately dependency-free and self-contained: each tool is its
own repo with its own venv, so it cannot import a shared package at runtime. It
resolves the palette by walking up for the shared file and falls back to the
values baked in below when the tool runs outside the umbrella checkout (packaged
builds, standalone installs).

Web tokens carry alpha over a black canvas; Qt stylesheets are inconsistent
about ``rgba()``, so every value is a solid hex flattened over ``#000000``.
"""

from __future__ import annotations

import json
import os
from typing import Any

PALETTE_RELPATH = os.path.join("assets", "themes", "theme_subjectivetechnologies.json")

# Flattened Subjective tokens — keep in sync with the shared JSON.
_FALLBACK: dict[str, Any] = {
    "colors": {
        "background": "#000000",        # --ivory
        "surface": "#0C0C0C",           # --ivory-2
        "panel": "#111111",             # --paper
        "foreground": "#FFFFFF",        # --ink
        "muted_text": "#949494",        # --ink-3
        "border": "#1F1F1F",            # --hairline
        "accent": "#FFFFFF",            # --gold (Subjective's single accent)
        "input_background": "#0C0C0C",
        "input_text": "#FFFFFF",
        "input_border": "#1F1F1F",
        "button_background": "#111111",
        "button_text": "#FFFFFF",
        "button_border": "#1F1F1F",
        "button_hover": "#1A1A1A",
        "button_pressed": "#0C0C0C",
        "scrollbar_background": "#0C0C0C",
        "scrollbar_handle": "#292929",
        "scrollbar_border": "#1F1F1F",
        "connection_list_selected_background": "#1A1A1A",
        "connection_list_selected_text": "#FFFFFF",
    },
    "fonts": {
        "global_font": "'Roboto Mono', 'Fira Mono', 'Consolas', 'Monaco', monospace",
        "global_weight": "normal",
    },
}


def _find_shared_palette(start: str | None = None) -> str | None:
    """Walk up from this file looking for the umbrella's shared palette."""
    current = os.path.abspath(start or os.path.dirname(__file__))
    while True:
        candidate = os.path.join(current, PALETTE_RELPATH)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def load_theme(path: str | None = None) -> dict[str, Any]:
    """Return the branding palette, falling back to the baked-in values."""
    candidate = path or os.environ.get("SUBJECTIVE_THEME_FILE") or _find_shared_palette()
    if candidate and os.path.isfile(candidate):
        try:
            with open(candidate, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            merged = {section: dict(values) for section, values in _FALLBACK.items()}
            for section in merged:
                merged[section].update(loaded.get(section) or {})
            return merged
        except Exception:
            pass  # unreadable/!json — the baked-in palette is still correct
    return {section: dict(values) for section, values in _FALLBACK.items()}


def colors(theme: dict[str, Any] | None = None) -> dict[str, str]:
    return dict((theme or load_theme())["colors"])


def fonts(theme: dict[str, Any] | None = None) -> dict[str, str]:
    return dict((theme or load_theme())["fonts"])
