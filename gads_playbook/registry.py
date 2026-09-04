"""Subcommand registry. Each module exposes register(sub, add_common)."""
from . import normalise, leakage, misallocate, windows, feedscore

MODULES = [normalise, leakage, misallocate, windows, feedscore]

def register_all(sub, add_common):
    for m in MODULES:
        m.register(sub, add_common)
