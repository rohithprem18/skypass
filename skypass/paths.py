"""Project locations, resolved from the package rather than the shell.

Every default output and cache path in this project is anchored here. The
alternative -- plain relative paths like "cache" -- resolves against the
working directory, so running an experiment from ``experiments/`` silently
built a second cache and a second results directory beside the first. Anchoring
on the package means one cache and one results tree no matter where a script is
launched from.
"""
from __future__ import annotations

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CACHE_DIR = os.path.join(PROJECT_ROOT, "cache")
SPACETRACK_CACHE_DIR = os.path.join(CACHE_DIR, "spacetrack")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
FIGURES_DIR = os.path.join(PROJECT_ROOT, "figures")
TLE_ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "tle_archive")
