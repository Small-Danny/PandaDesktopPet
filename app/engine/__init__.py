"""engine — UI-free core services (state coordination, scheduling, cameo, assets).

Modules in this package MUST NOT import tkinter, PIL or pystray so they can be
unit-tested headless. UI layers (main.py, bubble.py, standby.py) adapt them.
"""
