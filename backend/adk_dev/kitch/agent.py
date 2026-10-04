"""Expose Kitch's real coordinator to the local ADK Web trace viewer.

This module adds no second agent topology.  It only adapts the existing root
agent to the directory convention expected by ``adk web``.
"""

from pathlib import Path
import sys


# ADK Web puts the agents directory—not the backend root—on sys.path.
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agent.core import kitch_coordinator


root_agent = kitch_coordinator
