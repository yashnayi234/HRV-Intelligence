"""pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
import os

# Ensure hrv-agent project root is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
