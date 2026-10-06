import os
import pytest
from backend.fastapi_app.core.analyzer import get_language, IGNORED_DIRS

def test_get_language():
    assert get_language("test.py") == "python"
    assert get_language("app.js") == "javascript"
    assert get_language("components.tsx") == "javascript"
    assert get_language("unknown.txt") == "unknown"

def test_ignored_dirs():
    assert ".git" in IGNORED_DIRS
    assert "node_modules" in IGNORED_DIRS
    assert "__pycache__" in IGNORED_DIRS
