"""Shared test setup.

The parser tests import ``atis_parser`` directly so they run without Home
Assistant; the integration tests import ``custom_components.aussie_atis``.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "custom_components" / "aussie_atis"))
