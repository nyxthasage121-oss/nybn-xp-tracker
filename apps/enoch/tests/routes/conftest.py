"""Route test configurations."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _ensure_enoch_bot():
    """Ensure Enoch.bot exists so patch() targets can resolve it."""
    with patch("Enoch.bot", MagicMock(), create=True):
        yield
