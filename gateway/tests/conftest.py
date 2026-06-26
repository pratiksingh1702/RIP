"""Pytest configuration for gateway tests."""

import os
import sys

# Add gateway directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
