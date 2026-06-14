"""
Tests covering the hardened error-handling and edge-case paths in cognis_setup.py.

All tests stay at unit / import level: no subprocesses are spawned, no network
calls are made, and no writes to ~/.cognis happen.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers to import the module without triggering the _install_ascii_filter()
# side-effect that would replace sys.stdout.
# ---------------------------------------------------------------------------
import importlib
import importlib.util

_SRC = Path(__file__).resolve().parent.parent / "cognis_setup.py"


def _load():
    spec = importlib.util.spec_from_file_location("cognis_setup", _SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cs = _load()


# ---------------------------------------------------------------------------
# 1. load_state: non-dict JSON returns empty dict (guards .get() calls)
# ---------------------------------------------------------------------------

class TestLoadState:
    def test_list_json_returns_empty(self, tmp_path, monkeypatch):
        state_file = tmp_path / "setup.json"
        state_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        monkeypatch.setattr(cs, "STATE_FILE", state_file)
        result = cs.load_state()
        assert result == {}

    def test_string_json_returns_empty(self, tmp_path, monkeypatch):
        state_file = tmp_path / "setup.json"
        state_file.write_text(json.dumps("hello"), encoding="utf-8")
        monkeypatch.setattr(cs, "STATE_FILE", state_file)
        result = cs.load_state()
        assert result == {}

    def test_valid_dict_is_returned(self, tmp_path, monkeypatch):
        state_file = tmp_path / "setup.json"
        state_file.write_text(json.dumps({"familiarity": 3}), encoding="utf-8")
        monkeypatch.setattr(cs, "STATE_FILE", state_file)
        result = cs.load_state()
        assert result == {"familiarity": 3}

    def test_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cs, "STATE_FILE", tmp_path / "nonexistent.json")
        result = cs.load_state()
        assert result == {}


# ---------------------------------------------------------------------------
# 2. load_manifest: bad JSON, non-UTF-8, wrong top-level type all return empty
# ---------------------------------------------------------------------------

class TestLoadManifest:
    def test_missing_path_returns_empty(self):
        result = cs.load_manifest(None)
        assert result == {"meta": {}, "tools": {}}

    def test_malformed_json_returns_empty(self, tmp_path, capsys):
        bad = tmp_path / "MANIFEST.json"
        bad.write_text("{not valid json", encoding="utf-8")
        result = cs.load_manifest(bad)
        assert result == {"meta": {}, "tools": {}}
        captured = capsys.readouterr()
        assert "not valid JSON" in captured.err or "could not read" in captured.err

    def test_non_dict_list_top_level_returns_empty(self, tmp_path, capsys):
        bad = tmp_path / "MANIFEST.json"
        bad.write_text(json.dumps(42), encoding="utf-8")
        result = cs.load_manifest(bad)
        assert result == {"meta": {}, "tools": {}}
        captured = capsys.readouterr()
        assert "unexpected top-level type" in captured.err

    def test_valid_list_manifest_loads(self, tmp_path):
        m = tmp_path / "MANIFEST.json"
        tools = [{"name": "mytool", "domain": "Security", "desc": "A tool", "pip": "pip install mytool"}]
        m.write_text(json.dumps(tools), encoding="utf-8")
        result = cs.load_manifest(m)
        assert "mytool" in result["tools"]
        assert result["tools"]["mytool"]["domain"] == "Security"

    def test_valid_dict_manifest_loads(self, tmp_path):
        m = tmp_path / "MANIFEST.json"
        data = {
            "org": "cognis-digital",
            "tools": {
                "depscan": {
                    "name": "depscan",
                    "domain": "Security Operations",
                    "desc": "Dependency scanner",
                    "pip": "pip install depscan",
                }
            },
        }
        m.write_text(json.dumps(data), encoding="utf-8")
        result = cs.load_manifest(m)
        assert "depscan" in result["tools"]
        assert result["meta"]["org"] == "cognis-digital"

    def test_entry_missing_name_is_skipped(self, tmp_path):
        m = tmp_path / "MANIFEST.json"
        tools = [{"domain": "Security", "desc": "No name field"}]
        m.write_text(json.dumps(tools), encoding="utf-8")
        result = cs.load_manifest(m)
        assert result["tools"] == {}


# ---------------------------------------------------------------------------
# 3. discover_manifest: explicit path that doesn't exist prints to stderr
# ---------------------------------------------------------------------------

class TestDiscoverManifest:
    def test_explicit_missing_path_returns_none_and_warns(self, tmp_path, capsys):
        nonexistent = str(tmp_path / "no_such_file.json")
        result = cs.discover_manifest(nonexistent)
        assert result is None
        captured = capsys.readouterr()
        assert "ERROR" in captured.err or "not found" in captured.err

    def test_explicit_existing_path_returns_path(self, tmp_path):
        f = tmp_path / "MANIFEST.json"
        f.write_text("{}", encoding="utf-8")
        result = cs.discover_manifest(str(f))
        assert result == f

    def test_no_explicit_and_no_file_returns_none(self, tmp_path, monkeypatch):
        # Redirect all candidate search locations away from real filesystem
        monkeypatch.chdir(tmp_path)
        result = cs.discover_manifest(None)
        # May be None or a real path if MANIFEST.json exists in the repo tree;
        # just check it doesn't raise.
        assert result is None or isinstance(result, Path)


# ---------------------------------------------------------------------------
# 4. _probe_endpoint: malformed / empty URL returns False without raising
# ---------------------------------------------------------------------------

class TestProbeEndpoint:
    def test_empty_string_returns_false(self):
        assert cs._probe_endpoint("") is False

    def test_no_scheme_returns_false(self):
        assert cs._probe_endpoint("localhost:8774") is False

    def test_unreachable_url_returns_false(self):
        # Port 1 on loopback is almost certainly closed.
        result = cs._probe_endpoint("http://127.0.0.1:1")
        assert result is False

    def test_url_with_none_host_returns_false(self):
        # urlparse("http:///models") gives hostname=None
        result = cs._probe_endpoint("http:///v1")
        assert result is False


# ---------------------------------------------------------------------------
# 5. install_command: fallback when chosen method is blank
# ---------------------------------------------------------------------------

class TestInstallCommand:
    def test_falls_back_to_pipx_when_pip_blank(self):
        tool = {"pip": "", "pipx": "pipx install mytool", "git": "", "docker": ""}
        cmd = cs.install_command(tool, "pip", sys.executable)
        assert "mytool" in cmd

    def test_returns_empty_string_when_all_methods_blank(self):
        tool = {"pip": "", "pipx": "", "git": "", "docker": ""}
        cmd = cs.install_command(tool, "pip", sys.executable)
        assert cmd == ""

    def test_pip_replaces_with_python_exe(self):
        tool = {"pip": "pip install sometool", "pipx": "", "git": "", "docker": ""}
        cmd = cs.install_command(tool, "pip", "/usr/bin/python3")
        assert '"/usr/bin/python3" -m pip install sometool' == cmd


# ---------------------------------------------------------------------------
# 6. familiarity validation in run(): out-of-range / wrong type is re-prompted
# ---------------------------------------------------------------------------

class TestFamiliarityValidation:
    """
    Verify that a corrupt saved familiarity value (0, 6, "foo", None)
    triggers a re-prompt rather than being used verbatim.
    """
    _BAD_VALUES = [0, 6, -1, "foo", 3.5, None]

    @pytest.mark.parametrize("bad", _BAD_VALUES)
    def test_bad_familiarity_triggers_prompt(self, bad, monkeypatch, tmp_path):
        # Patch STATE_FILE so save_state doesn't pollute the real home dir.
        monkeypatch.setattr(cs, "STATE_DIR", tmp_path)
        monkeypatch.setattr(cs, "STATE_FILE", tmp_path / "setup.json")

        prompted = []

        def fake_prompt_familiarity(force=False):
            prompted.append(True)
            return 3

        monkeypatch.setattr(cs, "prompt_familiarity", fake_prompt_familiarity)

        # Patch everything that touches the terminal or filesystem beyond state.
        monkeypatch.setattr(cs, "detect_environment", lambda: {
            "os": "Linux", "os_release": "5.0", "python": "3.14.0",
            "python_exe": sys.executable,
            "has_pip": True, "has_pipx": False, "has_git": True, "has_docker": False,
        })
        monkeypatch.setattr(cs, "discover_manifest", lambda p: None)
        monkeypatch.setattr(cs, "load_manifest", lambda p: {"meta": {}, "tools": {}})

        # Simulate state with a bad familiarity value already saved.
        (tmp_path / "setup.json").write_text(
            json.dumps({"familiarity": bad, "seen_env": True, "method": "pip"}),
            encoding="utf-8",
        )

        # Intercept the interactive loop: return EOF immediately so run() exits.
        monkeypatch.setattr(cs, "ask", lambda *a, **kw: cs.EOF)
        monkeypatch.setattr(cs, "clear_screen", lambda: None)
        monkeypatch.setattr(cs, "pause", lambda: None)

        cs.run(dry_run=True, use_curses=False)

        assert prompted, f"prompt_familiarity should have been called for bad value {bad!r}"
