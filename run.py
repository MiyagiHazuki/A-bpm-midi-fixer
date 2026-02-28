#!/usr/bin/env python3
"""
MIDI Repair Tool Launcher

This script provides easy access to both CLI and GUI interfaces.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def main():
    if len(sys.argv) > 1:
        # Run CLI
        from midi_repair.cli import main as cli_main

        sys.exit(cli_main())
    else:
        # Run GUI (with BPM visualization)
        from midi_repair.app import main as gui_main

        gui_main()


if __name__ == "__main__":
    main()
