"""Fusion: blend soft signals + apply hard-gate floors -> score/band/reason."""

from .fuse import FusionResult, fuse

__all__ = ["fuse", "FusionResult"]
