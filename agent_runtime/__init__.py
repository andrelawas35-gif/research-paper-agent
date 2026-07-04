"""Agent runtime package — extracted modules from agent.py.

This package exists to reduce agent.py to a composition module.
Each module owns a coherent slice of implementation behind a small
public interface.  See docs/python-module-architecture-plan.md.
"""

from __future__ import annotations
