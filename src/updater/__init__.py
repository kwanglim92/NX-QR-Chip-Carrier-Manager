"""Installer-based auto-update entrypoint."""

from src.updater.client import check_and_apply

__all__ = ["check_and_apply"]
