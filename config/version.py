"""Single source of truth for app version — reads root VERSION file."""
from pathlib import Path


def get_version(default="0.0.0-dev"):
    try:
        return (Path(__file__).resolve().parent.parent / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
    except OSError:
        return default
