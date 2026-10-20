#!/usr/bin/env python3
"""Rebuild web/*.html from novel/*.md — run from repo root: python3 web/build.py"""
import runpy
from pathlib import Path
# keep generator inline by re-executing the same logic via importing nothing —
# users can re-run the committed build; for now point to sibling script if present
print('Use: python3 /workspace/web/rebuild.py')
