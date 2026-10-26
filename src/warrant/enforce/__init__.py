"""Enforcement backends. ``gate`` holds the shared decision logic; backends apply it."""

from .gate import Decision, Gate, allow_all

__all__ = ["Decision", "Gate", "allow_all"]
