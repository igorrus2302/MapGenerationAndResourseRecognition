"""Minimal synthetic geological map generator and offline viewer."""

from .generator import generate_map, load_config, save_map
from .viewer import build_viewer

__all__ = ["build_viewer", "generate_map", "load_config", "save_map"]
