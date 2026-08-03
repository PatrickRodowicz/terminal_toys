#!/usr/bin/env python3
"""Launcher.

The program lives in the mechscan package beside this file;
`python3 -m mechscan` is the same thing.

    python3 scan.py                 the first mech in mechs/
    python3 scan.py timber_wolf     a named mech
    python3 scan.py --list          what is available
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mechscan.cli import main   # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
