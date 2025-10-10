"""Pytest configuration for profiling tests."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import setup_profiling_data to register profiling bundles
# This ensures bundles are registered before tests run
try:
    from scripts.profiling import setup_profiling_data  # noqa: F401
except ImportError:
    # If import fails, bundles may already be registered or not available
    pass
