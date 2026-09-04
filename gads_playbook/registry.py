"""Subcommand registry. Each module exposes register(sub, add_common)."""
from . import normalise

MODULES = [normalise]

def register_all(sub, add_common):
    for m in MODULES:
        m.register(sub, add_common)
