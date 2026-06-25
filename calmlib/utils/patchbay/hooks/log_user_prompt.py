#!/usr/bin/env python3
"""DISABLED 2026-05-28 — the previous body was crashing on every UserPromptSubmit
event. Hook is reduced to a no-op so it can't error regardless of where it's
wired. Original implementation in git history.
"""

import sys

if __name__ == "__main__":
    try:
        sys.stdin.read()
    except Exception:
        pass
    sys.exit(0)
