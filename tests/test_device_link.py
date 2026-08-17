Exit code: 0
Wall time: 0.8 seconds
Output:
"""Tests for the device configuration link."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

PACKAGE_NAME = "custom_components.dcs_server_bot"
if PACKAGE_NAME not in sys.modules:
    package = types.ModuleType(PACKAGE_NAME)
    package.__path__ = [str(Path(__file__).parents[1] / "custom_components" / "dcs_server_bot")]
    sys.modules[PACKAGE_NAME] = package

const = importlib.import_module(f"{PACKAGE_NAME}.const")


def test_configuration_url_opens_home_assistant_integration() -> None:
    """The Visit link must not point at the RestAPI root, which has no UI."""
    assert const.CONFIGURATION_URL == (
        "homeassistant://config/integrations/integration/dcs_server_bot"
    )

