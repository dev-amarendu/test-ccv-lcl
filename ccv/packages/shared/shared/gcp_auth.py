"""Shared GCP credentials helper.

Loads credentials from the service account JSON file specified in
``GOOGLE_APPLICATION_CREDENTIALS`` (via config) and provides a
reusable ``get_credentials()`` function for all GCP clients.
"""

from __future__ import annotations

from google.auth.credentials import Credentials
from google.oauth2 import service_account

from shared.config import get_settings

_credentials: Credentials | None = None


def get_credentials() -> Credentials | None:
    """Return credentials from the service account JSON, or None for ADC fallback."""
    global _credentials
    if _credentials is not None:
        return _credentials

    settings = get_settings()
    sa_path = settings.google_application_credentials

    if not sa_path:
        # Fall back to Application Default Credentials
        return None

    _credentials = service_account.Credentials.from_service_account_file(sa_path)
    return _credentials
