"""
conftest.py — Add the project root to sys.path so that
`from scripts.X import Y` works in tests.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
