#!/usr/bin/env python3
"""
cognis_setup.py — the canonical Cognis guided SETUP WIZARD.

A polished, zero-dependency (stdlib-only) CLI/TUI that walks a beginner through
installing the Cognis tool suite. Type numbers in a menu; everything is
explained at the depth you ask for (familiarity 1-5).

Run it:
    python cognis_setup.py
    python cognis_setup.py --manifest path/to/MANIFEST.json
    python cognis_setup.py --dry-run          # print commands, never run them

Import it:
    from cognis_setup import run
    run(manifest_path="MANIFEST.json")

Design goals
------------
- NO third-party dependencies. Pure stdlib.
- Degrades gracefully: NO_COLOR / non-tty / dumb terminals lose color, not
  function. Optional full-screen curses menu on POSIX; ANSI numbered menu
  everywhere else (incl. Windows without curses).
- Every action is GUIDED: explain -> show EXACT command -> confirm [Y/n] ->
  run via subprocess -> report clearly -> back to menu.
- Nothing destructive happens without explicit confirmation. --dry-run never
  executes anything.

The wizard tolerates a missing or malformed MANIFEST.json: it still offers the
local-AI-fleet setup, configuration, health-check and help.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Decorative Unicode -> ASCII map for terminals whose encoding can't represent
# them (legacy Windows cp1252, redirected pipes). Keeps output clean instead of
# emitting replacement glyphs or crashing on UnicodeEncodeError.
_ASCII_FALLBACK = {
    "—": "-", "–": "-", "·": "-", "•": "-", "✓": "OK", "✗": "X",
    "↑": "^", "↓": "v", "→": "->", "…": "...",
    "╔": "+", "╗": "+", "╚": "+", "╝": "+", "║": "|", "═": "-",
    "“": '"', "”": '"', "’": "'", "‘": "'",
}


def _encoding_ok() -> bool:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        "—·•✓✗╔═".encode(enc)
        return True
    except Exception:
        return False


def _install_ascii_filter() -> None:
    """If the console can't encode our decorative glyphs, transliterate them."""
    if _encoding_ok():
        return

    class _AsciiWriter:
        def __init__(self, base):
            self._base = base

        def write(self, s):
            if isinstance(s, str):
                for k, v in _ASCII_FALLBACK.items():
                    if k in s:
                        s = s.replace(k, v)
            return self._base.write(s)

        def __getattr__(self, name):
            return getattr(self._base, name)

    try:
        sys.stdout = _AsciiWriter(sys.stdout)
        sys.stderr = _AsciiWriter(sys.stderr)
    except Exception:
        # Last resort: at least don't crash on unencodable chars.
        try:
            sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


_install_ascii_filter()

APP_NAME = "Cognis Setup Wizard"
APP_VERSION = "1.0"
STATE_DIR = Path.home() / ".cognis"
STATE_FILE = STATE_DIR / "setup.json"

# A curated "starter bundle" — the friendliest first install. Names are matched
# against the manifest case-insensitively; missing names are silently skipped.
STARTER_BUNDLE = [
    "depscan", "secretscan", "iacscan", "sastlite", "licensecheck",
    "osintkit", "logtriage", "phishcheck",
]

# Local AI fleet presets — kept in sync with cognis_ai_backend.py / INTEGRATION.md.
AI_PRESETS = {
    "uncensored-fleet": {
        "base_url": "http://127.0.0.1:8774/v1",
        "model": "Josiefied-Qwen3-8B-abliterated",
        "blurb": "The local abliterated 'commander' slot (fleet up uncensored), port 8774.",
    },
    "cognis-code": {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "coder",
        "blurb": "The cognis-code coding server (cognis-code serve), port 11434.",
    },
}

GLOSSARY = [
    ("pip", "Python's package installer. Installs libraries/tools into your Python environment."),
    ("pipx", "Installs Python CLI apps in isolated environments so they don't clash. Best for command-line tools."),
    ("git", "Version control. Here it's used to install tools straight from a source repository."),
    ("docker", "Runs a tool inside a self-contained container — no Python setup needed, but Docker must be running."),
    ("manifest", "The MANIFEST.json file: the master list of every Cognis tool and how to install each one."),
    ("domain", "A category of tools (e.g. 'Security Operations', 'FinTech', 'Defense Tech')."),
    ("fleet", "The LOCAL AI models that power scanners' optional --ai mode. Everything stays on your machine."),
    ("dry run", "A safe preview: the wizard prints the EXACT command it WOULD run, but does not run it."),
    ("venv", "A 'virtual environment' — an isolated sandbox for Python packages so installs stay tidy."),
]


# --------------------------------------------------------------------------- #
# Terminal styling (degrades gracefully)
# --------------------------------------------------------------------------- #

class Style:
    """ANSI styling that turns itself off on dumb/no-color/non-tty terminals."""

    def __init__(self) -> None:
        self.enabled = self._color_ok()

    @staticmethod
    def _color_ok() -> bool:
        if os.environ.get("NO_COLOR") is not None:
            return False
        if os.environ.get("TERM", "") == "dumb":
            return False
        if not sys.stdout.isatty():
            return False
        # Modern Windows terminals support ANSI; older cmd may not. Try to enable.
        if os.name == "nt":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except Exception:
                return False
        return True

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    # ASCII-safe symbols when the terminal can't render Unicode (cp1252, dumb).
    @property
    def check(self) -> str: return "✓" if self.enabled else "OK"
    @property
    def cross(self) -> str: return "✗" if self.enabled else "X"
    @property
    def bullet(self) -> str: return "•" if self.enabled else "-"
    @property
    def dash(self) -> str: return "—" if self.enabled else "-"

    def bold(self, t: str) -> str:    return self._wrap("1", t)
    def dim(self, t: str) -> str:     return self._wrap("2", t)
    def red(self, t: str) -> str:     return self._wrap("31", t)
    def green(self, t: str) -> str:   return self._wrap("32", t)
    def yellow(self, t: str) -> str:  return self._wrap("33", t)
    def blue(self, t: str) -> str:    return self._wrap("34", t)
    def magenta(self, t: str) -> str: return self._wrap("35", t)
    def cyan(self, t: str) -> str:    return self._wrap("36", t)


S = Style()


def clear_screen() -> None:
    """Clear the screen when we own a real terminal; otherwise just space down."""
    if not sys.stdout.isatty():
        print("\n" * 2)
        return
    if S.enabled:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
    else:
        os.system("cls" if os.name == "nt" else "clear")


def box(title: str, subtitle: str = "") -> None:
    """Draw a clean box-drawing header."""
    width = 64
    top = "╔" + "═" * (width - 2) + "╗"
    bot = "╚" + "═" * (width - 2) + "╝"
    if not S.enabled:  # ASCII fallback for terminals that mangle box chars
        top = "+" + "-" * (width - 2) + "+"
        bot = "+" + "-" * (width - 2) + "+"
        side = "|"
    else:
        side = "║"

    def row(text: str, styler=lambda x: x) -> str:
        pad = width - 2 - len(text)
        pad = max(pad, 0)
        return side + styler(" " + text + " " * (pad - 1)) + side

    print(S.cyan(top))
    print(S.cyan(row(title, S.bold)))
    if subtitle:
        print(S.cyan(row(subtitle, S.dim)))
    print(S.cyan(bot))


def rule() -> None:
    print(S.dim("─" * 64 if S.enabled else "-" * 64))


# --------------------------------------------------------------------------- #
# Familiarity-aware explanation
# --------------------------------------------------------------------------- #

def guide(level: int, by_level: dict) -> str:
    """
    Return the explanation appropriate for the user's familiarity `level` (1-5).

    `by_level` maps anchor levels to text, e.g. {1: "...", 3: "...", 5: "..."}.
    We pick the text for the highest anchor that is <= level (falling back to
    the lowest anchor if level is below all of them).
    """
    if not by_level:
        return ""
    anchors = sorted(by_level)
    chosen = anchors[0]
    for a in anchors:
        if a <= level:
            chosen = a
    return by_level[chosen]


def explain(level: int, by_level: dict) -> None:
    """Print the level-appropriate explanation (skip if empty)."""
    text = guide(level, by_level)
    if text:
        print(S.dim(text) if level >= 4 else text)
        print()


# --------------------------------------------------------------------------- #
# State (familiarity persistence)
# --------------------------------------------------------------------------- #

def load_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def save_state(state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:  # never crash on a read-only home dir
        print(S.yellow(f"  (could not save settings: {exc})"))


# --------------------------------------------------------------------------- #
# Input helpers
# --------------------------------------------------------------------------- #

# Sentinel returned by ask() when stdin reaches EOF (piped input ran out, Ctrl-D).
# The main loop treats it as "exit cleanly" instead of spinning forever.
EOF = object()

# Strip a leading byte-order-mark in any of its forms: the real U+FEFF, and the
# mojibake "ï»¿" that appears when a UTF-8 BOM is decoded as cp1252 (e.g. when a
# PowerShell pipe feeds stdin). Real interactive terminals never send these.
_BOM_PREFIXES = ("﻿", "ï»¿", "\xef\xbb\xbf")


def _clean_input(text: str) -> str:
    for bom in _BOM_PREFIXES:
        if text.startswith(bom):
            text = text[len(bom):]
    return text.strip()


def ask(prompt: str, default: str = ""):
    suffix = f" [{default}]" if default else ""
    try:
        raw = _clean_input(input(S.bold(f"{prompt}{suffix}: ")))
    except EOFError:
        print()
        return EOF
    except KeyboardInterrupt:
        print()
        return EOF
    return raw or default


def confirm(prompt: str, default_yes: bool = True) -> bool:
    hint = "[Y/n]" if default_yes else "[y/N]"
    try:
        raw = _clean_input(input(S.bold(f"{prompt} {hint} "))).lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not raw:
        return default_yes
    return raw in ("y", "yes")


def pause() -> None:
    try:
        input(S.dim("\nPress Enter to return to the menu… "))
    except (EOFError, KeyboardInterrupt):
        print()


# --------------------------------------------------------------------------- #
# Environment detection
# --------------------------------------------------------------------------- #

def detect_environment() -> dict:
    """Detect OS, Python, and which install backends exist on PATH."""
    backends = {name: shutil.which(name) for name in ("pip", "pip3", "pipx", "git", "docker")}
    # `pip` may only be runnable as `python -m pip`; treat that as available too.
    has_pip = bool(backends["pip"] or backends["pip3"])
    if not has_pip:
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"],
                           capture_output=True, timeout=10)
            has_pip = True
        except Exception:
            has_pip = False
    return {
        "os": platform.system() or os.name,
        "os_release": platform.release(),
        "python": platform.python_version(),
        "python_exe": sys.executable,
        "has_pip": has_pip,
        "has_pipx": bool(backends["pipx"]),
        "has_git": bool(backends["git"]),
        "has_docker": bool(backends["docker"]),
    }


def recommend_method(env: dict) -> str:
    """Pick the friendliest available install method."""
    if env["has_pipx"]:
        return "pipx"
    if env["has_pip"]:
        return "pip"
    if env["has_git"]:
        return "git"
    if env["has_docker"]:
        return "docker"
    return "pip"  # last resort; we'll warn the user


def print_environment(env: dict, level: int) -> None:
    box("Your environment", "what the wizard detected on this machine")
    ok = lambda b: S.green(S.check + " yes") if b else S.red(S.cross + " no")
    print(f"  Operating system : {S.bold(env['os'])} {env['os_release']}")
    print(f"  Python           : {S.bold(env['python'])}  ({env['python_exe']})")
    print(f"  pip              : {ok(env['has_pip'])}")
    print(f"  pipx             : {ok(env['has_pipx'])}")
    print(f"  git              : {ok(env['has_git'])}")
    print(f"  docker           : {ok(env['has_docker'])}")
    print()
    rec = recommend_method(env)
    print("  " + S.cyan(f"Recommended install method: {S.bold(rec)}"))
    explain(level, {
        1: ("  Why this matters: tools can be installed several ways. The wizard\n"
            "  picked the easiest one available to you. pipx keeps each tool\n"
            "  tidy and separate; pip is the standard Python installer; git\n"
            "  builds from source; docker runs tools in a sealed container."),
        3: "  pipx is preferred (isolated CLI installs); pip is the fallback.",
        5: f"  rec={rec}; override in Configure (6).",
    })
    if not (env["has_pip"] or env["has_pipx"] or env["has_git"] or env["has_docker"]):
        print(S.red("\n  WARNING: no install backend found on PATH. Install Python's pip,\n"
                     "  pipx, git, or Docker before installing tools."))


# --------------------------------------------------------------------------- #
# Manifest loading
# --------------------------------------------------------------------------- #

def discover_manifest(explicit: str | None) -> Path | None:
    """Find a MANIFEST.json: explicit arg, then a few sensible locations."""
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_file():
            print(
                S.red(f"  ERROR: manifest not found: {p}"),
                file=sys.stderr,
            )
            return None
        return p

    here = Path(__file__).resolve().parent
    candidates = [
        Path.cwd() / "MANIFEST.json",
        here / "MANIFEST.json",
        here.parent / "MANIFEST.json",
        here.parent.parent / "_meta" / "cognis-arsenal" / "MANIFEST.json",
        here.parent.parent.parent / "_meta" / "cognis-arsenal" / "MANIFEST.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def load_manifest(path: Path | None) -> dict:
    """
    Load and normalize a manifest into:
        {"meta": {...}, "tools": {name: {name,domain,desc,pip,pipx,git,docker,repo}}}
    Tolerant of both list-of-tools and dict-of-tools shapes, and of the
    repo/repo_url field naming difference.
    """
    empty = {"meta": {}, "tools": {}}
    if not path:
        return empty
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        print(S.yellow(f"  (manifest is not valid UTF-8: {path})"), file=sys.stderr)
        return empty
    except json.JSONDecodeError as exc:
        print(S.yellow(f"  (manifest is not valid JSON: {path}: {exc})"), file=sys.stderr)
        return empty
    except Exception as exc:
        print(S.yellow(f"  (could not read manifest {path}: {exc})"), file=sys.stderr)
        return empty

    if not isinstance(raw, (dict, list)):
        print(
            S.yellow(f"  (manifest has unexpected top-level type {type(raw).__name__}: {path})"),
            file=sys.stderr,
        )
        return empty

    raw_tools = raw.get("tools", raw) if isinstance(raw, dict) else raw
    tools: dict[str, dict] = {}

    def add(entry: dict) -> None:
        if not isinstance(entry, dict):
            return
        name = entry.get("name")
        if not name:
            return
        tools[name] = {
            "name": name,
            "domain": entry.get("domain_label") or entry.get("domain") or "Other",
            "desc": entry.get("desc", "") or "",
            "repo": entry.get("repo_url") or entry.get("repo") or "",
            "pip": entry.get("pip", ""),
            "pipx": entry.get("pipx", ""),
            "git": entry.get("git", ""),
            "docker": entry.get("docker", ""),
        }

    if isinstance(raw_tools, dict):
        for key, entry in raw_tools.items():
            if isinstance(entry, dict):
                entry.setdefault("name", key)
                add(entry)
    elif isinstance(raw_tools, list):
        for entry in raw_tools:
            add(entry)

    meta = {}
    if isinstance(raw, dict):
        meta = {k: raw[k] for k in ("org", "raw_base", "sources_repo", "total") if k in raw}
    return {"meta": meta, "tools": tools}


# --------------------------------------------------------------------------- #
# Install command resolution + execution
# --------------------------------------------------------------------------- #

def install_command(tool: dict, method: str, python_exe: str) -> str:
    """Return the exact shell command string for a tool under `method`."""
    cmd = tool.get(method, "")
    if method == "pip" and cmd:
        # Prefer the running interpreter so the user's active venv is honored.
        return cmd.replace("pip install", f'"{python_exe}" -m pip install', 1)
    if not cmd:
        # Fall back through methods if the chosen one is blank.
        for alt in ("pipx", "pip", "git", "docker"):
            if tool.get(alt):
                return install_command(tool, alt, python_exe)
    return cmd


def run_command(command: str, dry_run: bool, level: int) -> bool:
    """Show the command, confirm, then run it (or just print it in dry-run)."""
    print()
    print("  " + S.yellow("EXACT command:"))
    print("    " + S.bold(command))
    print()

    if dry_run:
        print(S.magenta("  [dry-run] not executing — this is a preview only."))
        return True

    explain(level, {
        1: ("  About to run the command above in your shell. It downloads and\n"
            "  installs software. If it fails, nothing is broken — you can\n"
            "  retry or pick a different install method in Configure."),
        4: "",
    })
    if not confirm("  Run this command now?", default_yes=True):
        print(S.dim("  Skipped."))
        return False

    print(S.dim("  Running…\n"))
    try:
        proc = subprocess.run(command, shell=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(S.red(f"  {S.cross} Command timed out after 300 s."))
        return False
    except Exception as exc:
        print(S.red(f"  {S.cross} Failed to launch command: {exc}"))
        return False

    if proc.returncode == 0:
        print(S.green(f"\n  {S.check} Success."))
        return True
    print(S.red(f"\n  {S.cross} Command exited with code {proc.returncode}."))
    explain(level, {
        1: ("  Common causes: the tool isn't published yet, no internet, or the\n"
            "  install method isn't available. Try menu 6 (Configure) to switch\n"
            "  methods, or menu 7 to health-check what you have."),
        4: "",
    })
    return False


def install_tools(tools: list[dict], method: str, env: dict, dry_run: bool, level: int) -> None:
    if not tools:
        print(S.yellow("  Nothing selected."))
        pause()
        return
    print()
    print(f"  Installing {S.bold(str(len(tools)))} tool(s) via {S.bold(method)}:")
    for t in tools:
        print(f"    {S.bullet} {t['name']}  {S.dim(S.dash + ' ' + (t['desc'][:54] if t['desc'] else t['domain']))}")
    if not dry_run and not confirm("\n  Proceed with this batch?", default_yes=True):
        print(S.dim("  Cancelled."))
        pause()
        return

    ok, fail = [], []
    for t in tools:
        rule()
        print(f"  {S.cyan(t['name'])} — {t['desc'] or t['domain']}")
        cmd = install_command(t, method, env["python_exe"])
        if not cmd:
            print(S.red(f"  {S.cross} No install command available for {t['name']}."))
            fail.append(t["name"])
            continue
        (ok if run_command(cmd, dry_run, level) else fail).append(t["name"])

    rule()
    print(f"  {S.green('Succeeded')}: {len(ok)}    {S.red('Failed/skipped')}: {len(fail)}")
    if fail:
        print(S.dim("  Not installed: " + ", ".join(fail)))
    pause()


# --------------------------------------------------------------------------- #
# Menu actions
# --------------------------------------------------------------------------- #

def action_quick_install(manifest, env, cfg, dry_run, level) -> None:
    clear_screen()
    box("1 · Quick install", "the recommended starter bundle")
    explain(level, {
        1: ("This installs a small, friendly set of the most useful Cognis tools so\n"
            "you can get going fast. You can always add more later from the menu.\n"
            "Each install is shown to you and confirmed before it runs."),
        3: "Installs a curated starter set. Each command is shown and confirmed.",
        5: "Starter bundle install via configured method.",
    })
    tools_by_lower = {n.lower(): t for n, t in manifest["tools"].items()}
    chosen = [tools_by_lower[n.lower()] for n in STARTER_BUNDLE if n.lower() in tools_by_lower]
    if not chosen:
        print(S.yellow("  The starter bundle isn't present in this manifest.\n"
                       "  Try menu 2 (Browse by category) or 3 (Pick individual tools)."))
        pause()
        return
    install_tools(chosen, cfg["method"], env, dry_run, level)


def action_browse_category(manifest, env, cfg, dry_run, level) -> None:
    domains: dict[str, list[dict]] = {}
    for t in manifest["tools"].values():
        domains.setdefault(t["domain"], []).append(t)
    if not domains:
        clear_screen()
        box("2 · Browse by category")
        print(S.yellow("  No tools available (manifest missing or empty)."))
        pause()
        return

    ordered = sorted(domains, key=lambda d: (-len(domains[d]), d.lower()))
    while True:
        clear_screen()
        box("2 · Browse by category", "pick a domain, then choose tools")
        explain(level, {
            1: "Tools are grouped by topic. Pick a number to see what's inside.",
            4: "",
        })
        for i, d in enumerate(ordered, 1):
            print(f"  {S.bold(str(i).rjust(2))}. {d}  {S.dim('(' + str(len(domains[d])) + ')')}")
        print(f"  {S.bold(' 0')}. Back")
        sel = ask("\n  Choose a category")
        if sel is EOF or sel in ("0", ""):
            return
        if not sel.isdigit() or not (1 <= int(sel) <= len(ordered)):
            continue
        domain = ordered[int(sel) - 1]
        _select_from_list(domains[domain], f"Category: {domain}", env, cfg, dry_run, level)


def action_pick_individual(manifest, env, cfg, dry_run, level) -> None:
    tools = sorted(manifest["tools"].values(), key=lambda t: t["name"].lower())
    if not tools:
        clear_screen()
        box("3 · Pick individual tools")
        print(S.yellow("  No tools available (manifest missing or empty)."))
        pause()
        return
    _select_from_list(tools, "All tools", env, cfg, dry_run, level, searchable=True)


def _select_from_list(tools, title, env, cfg, dry_run, level, searchable=False) -> None:
    view = list(tools)
    while True:
        clear_screen()
        box(f"{title}", "type numbers (e.g. 1,3,5) · 's term' to search · 0 back")
        for i, t in enumerate(view, 1):
            desc = t["desc"][:50] if t["desc"] else t["domain"]
            print(f"  {S.bold(str(i).rjust(3))}. {S.cyan(t['name'].ljust(16))} {S.dim(desc)}")
        print(f"  {S.bold('  0')}. Back")
        explain(level, {
            1: ("\n  Tip: enter one or more numbers separated by commas to choose\n"
                "  tools. Each one is explained and confirmed before installing."),
            4: "",
        })
        sel = ask("\n  Selection")
        if sel is EOF or sel in ("0", ""):
            return
        if searchable and sel.lower().startswith("s "):
            term = sel[2:].strip().lower()
            view = [t for t in tools if term in t["name"].lower() or term in t["desc"].lower()] or list(tools)
            continue
        picks = []
        for part in sel.replace(" ", ",").split(","):
            if part.isdigit() and 1 <= int(part) <= len(view):
                picks.append(view[int(part) - 1])
        if picks:
            install_tools(picks, cfg["method"], env, dry_run, level)
            return


def action_install_everything(manifest, env, cfg, dry_run, level) -> None:
    clear_screen()
    box("4 · Install everything", "the entire Cognis suite")
    tools = sorted(manifest["tools"].values(), key=lambda t: t["name"].lower())
    if not tools:
        print(S.yellow("  No tools available (manifest missing or empty)."))
        pause()
        return
    explain(level, {
        1: (f"This installs ALL {len(tools)} tools. That can take a while and use\n"
            "disk space and bandwidth. Every command is still shown; you confirm\n"
            "the whole batch once, then each install runs in turn."),
        3: f"Installs all {len(tools)} tools via {cfg['method']}. One batch confirm.",
        5: f"all={len(tools)} via {cfg['method']}.",
    })
    if dry_run or confirm(f"\n  Really install all {len(tools)} tools?", default_yes=False):
        install_tools(tools, cfg["method"], env, dry_run, level)
    else:
        print(S.dim("  Cancelled."))
        pause()


def action_setup_fleet(env, cfg, dry_run, level) -> None:
    clear_screen()
    box("5 · Set up the local AI fleet", "powers scanners' optional --ai mode")
    explain(level, {
        1: ("Some scanners can use a LOCAL AI model for deeper analysis. Nothing\n"
            "leaves your computer. This step doesn't download models — it points\n"
            "the scanners at a fleet you run yourself, by setting COGNIS_AI_*\n"
            "environment variables. With no fleet running, scanners stay 100%\n"
            "deterministic, which is perfectly fine."),
        3: ("Configures COGNIS_AI_* env so scanners' --ai mode targets a local,\n"
            "OpenAI-compatible fleet endpoint. Doesn't pull models."),
        5: "Exports COGNIS_AI_BACKEND/BASE_URL/MODEL for the chosen preset.",
    })
    presets = list(AI_PRESETS)
    for i, name in enumerate(presets, 1):
        p = AI_PRESETS[name]
        print(f"  {S.bold(str(i))}. {S.cyan(name)}")
        print(f"       {p['base_url']}  · model {p['model']}")
        print(f"       {S.dim(p['blurb'])}")
    print(f"  {S.bold('0')}. Back")
    sel = ask("\n  Choose a preset")
    if sel is EOF or sel in ("0", "") or not sel.isdigit() or not (1 <= int(sel) <= len(presets)):
        return
    name = presets[int(sel) - 1]
    p = AI_PRESETS[name]

    exports = {
        "COGNIS_AI_BACKEND": name,
        "COGNIS_AI_BASE_URL": p["base_url"],
        "COGNIS_AI_MODEL": p["model"],
    }
    print()
    print("  " + S.yellow("Set these environment variables:"))
    if os.name == "nt":
        for k, v in exports.items():
            print("    " + S.bold(f'setx {k} "{v}"'))
        print(S.dim("    (PowerShell session only: $env:COGNIS_AI_BACKEND = \"%s\")" % name))
    else:
        for k, v in exports.items():
            print("    " + S.bold(f'export {k}="{v}"'))

    if not dry_run:
        # Apply to THIS process so an immediate health-check / scanner works now.
        os.environ.update(exports)
        print(S.green(f"\n  {S.check} Applied to the current session."))
        if os.name == "nt" and confirm("  Also persist with setx (new shells)?", default_yes=False):
            for k, v in exports.items():
                try:
                    subprocess.run(["setx", k, v], capture_output=True)
                except Exception as exc:
                    print(S.red(f"    {S.cross} setx {k}: {exc}"))
            print(S.green(f"  {S.check} Persisted (open a new terminal to pick them up)."))
        else:
            explain(level, {
                1: ("\n  To make these stick across reboots, add the export/setx lines\n"
                    "  above to your shell profile (~/.bashrc) or run setx."),
                4: "",
            })
    else:
        print(S.magenta("\n  [dry-run] not setting anything."))
    pause()


def action_configure(env, cfg, level) -> None:
    methods = ["pip", "pipx", "git", "docker"]
    while True:
        clear_screen()
        box("6 · Configure", "install method and install location")
        print(f"  Current install method : {S.bold(cfg['method'])}")
        print(f"  Current install dir    : {S.bold(cfg.get('install_dir') or '(default / system)')}")
        print()
        print(f"  {S.bold('1')}. Change install method")
        print(f"  {S.bold('2')}. Change install directory (for git/source installs)")
        print(f"  {S.bold('0')}. Back")
        sel = ask("\n  Choose")
        if sel is EOF or sel in ("0", ""):
            return
        if sel == "1":
            explain(level, {
                1: ("\n  pipx = tidy isolated CLI tools (recommended). pip = standard.\n"
                    "  git = build from source. docker = run in a container."),
                4: "",
            })
            avail = {"pip": env["has_pip"], "pipx": env["has_pipx"],
                     "git": env["has_git"], "docker": env["has_docker"]}
            for i, m in enumerate(methods, 1):
                tag = S.green("(available)") if avail[m] else S.red("(not found)")
                print(f"    {S.bold(str(i))}. {m} {tag}")
            m = ask("  Method number")
            if m is not EOF and m.isdigit() and 1 <= int(m) <= len(methods):
                cfg["method"] = methods[int(m) - 1]
        elif sel == "2":
            d = ask("  Install directory (blank = default)", cfg.get("install_dir", ""))
            if d is not EOF:
                cfg["install_dir"] = d


def action_health_check(manifest, env, level) -> None:
    clear_screen()
    box("7 · Verify & health-check", "what's installed and reachable")
    explain(level, {
        1: ("Checks whether installed Cognis commands can be found on your PATH,\n"
            "and whether your AI fleet endpoint (if configured) is reachable.\n"
            "Nothing is installed or changed here — it's read-only."),
        4: "",
    })
    rule()
    print("  " + S.bold("Install backends:"))
    for name in ("pip", "pipx", "git", "docker"):
        present = env[f"has_{name}"]
        print(f"    {name.ljust(8)} {S.green(S.check) if present else S.red(S.cross)}")

    rule()
    print("  " + S.bold("Cognis commands on PATH:"))
    names = list(manifest["tools"]) or ["cognis"]
    found = 0
    for n in sorted(names)[:60]:
        loc = shutil.which(n)
        if loc:
            found += 1
            print(f"    {S.green(S.check)} {n}  {S.dim(loc)}")
    print(f"    {S.dim('Found ' + str(found) + ' of ' + str(len(names)) + ' tool command(s) on PATH.')}")

    rule()
    print("  " + S.bold("Local AI fleet:"))
    base = os.environ.get("COGNIS_AI_BASE_URL")
    if not base:
        print(S.dim("    Not configured (scanners run deterministically). See menu 5."))
    else:
        print(f"    Endpoint: {base}")
        ok = _probe_endpoint(base)
        print("    " + (S.green(S.check + " reachable") if ok
                        else S.red(S.cross + " not reachable (is the fleet up?)")))
    pause()


def _probe_endpoint(base_url: str) -> bool:
    """Best-effort TCP/HTTP probe of an OpenAI-compatible base URL."""
    if not base_url or "://" not in base_url:
        return False
    import urllib.request
    url = base_url.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status < 500
    except Exception:
        # A connection refused vs. 404 both tell us little; treat any reach as ok.
        try:
            from urllib.parse import urlparse
            import socket
            u = urlparse(base_url)
            host = u.hostname
            port = u.port or (443 if u.scheme == "https" else 80)
            if not host:
                return False
            with socket.create_connection((host, port), timeout=5):
                return True
        except Exception:
            return False


def action_help(level) -> None:
    clear_screen()
    box("8 · Help / glossary", "plain-language definitions")
    explain(level, {
        1: ("New to all this? Read these once and the menus will make sense.\n"
            "You never have to memorize commands — the wizard shows each one."),
        4: "",
    })
    for term, meaning in GLOSSARY:
        print(f"  {S.cyan(S.bold(term))}")
        print(f"    {meaning}")
    rule()
    print(S.dim("  Re-run anytime:  python cognis_setup.py"))
    print(S.dim("  Safe preview:    python cognis_setup.py --dry-run"))
    print(S.dim("  Custom manifest: python cognis_setup.py --manifest path/to/MANIFEST.json"))
    pause()


def action_change_familiarity(cfg) -> int:
    level = prompt_familiarity(force=True)
    cfg["familiarity"] = level
    return level


# --------------------------------------------------------------------------- #
# Familiarity prompt (Step 0)
# --------------------------------------------------------------------------- #

def prompt_familiarity(force: bool = False) -> int:
    clear_screen()
    box("How familiar are you with the terminal?",
        "this sets how much the wizard explains")
    print("  " + S.bold("1") + "  Barely touched a terminal " + S.dash + " explain everything.")
    print("  " + S.bold("2") + "  I can copy-paste commands.")
    print("  " + S.bold("3") + "  Comfortable; I know pip and basic CLI.")
    print("  " + S.bold("4") + "  Confident developer.")
    print("  " + S.bold("5") + "  Expert " + S.dash + " keep it terse.")
    print()
    while True:
        sel = ask("  Your level (1-5)", "3")
        if sel is EOF:           # piped input ran out / Ctrl-D: take a safe default
            return 3
        if sel.isdigit() and 1 <= int(sel) <= 5:
            return int(sel)
        if not force and sel == "":
            return 3


# --------------------------------------------------------------------------- #
# Optional curses front-end (POSIX). Falls back automatically if unavailable.
# --------------------------------------------------------------------------- #

def _curses_available() -> bool:
    if os.name == "nt":
        return False
    if not sys.stdout.isatty():
        return False
    try:
        import curses  # noqa: F401
        return True
    except Exception:
        return False


def curses_main_menu(items: list[str]) -> int:
    """Full-screen arrow-key menu. Returns the chosen index, or -1 to exit."""
    import curses

    def _draw(stdscr) -> int:
        curses.curs_set(0)
        idx = 0
        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            title = f"{APP_NAME} {APP_VERSION}"
            stdscr.addstr(1, max(2, (w - len(title)) // 2), title, curses.A_BOLD)
            stdscr.addstr(2, 2, "↑/↓ to move · Enter to select · q to quit")
            for i, label in enumerate(items):
                attr = curses.A_REVERSE if i == idx else curses.A_NORMAL
                stdscr.addstr(4 + i, 4, label[: w - 8], attr)
            stdscr.refresh()
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(items)
            elif key in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(items)
            elif key in (curses.KEY_ENTER, 10, 13):
                return idx
            elif key in (ord("q"), 27):
                return -1

    try:
        return curses.wrapper(_draw)
    except Exception:
        return -2  # signal: fall back to ANSI menu


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #

# (number, label) — the separator is rendered per-terminal so we never emit a
# glyph the console can't encode.
MENU_ITEMS = [
    ("1", "Quick install (recommended starter bundle)"),
    ("2", "Browse by category"),
    ("3", "Pick individual tools"),
    ("4", "Install everything"),
    ("5", "Set up the local AI fleet (--ai mode)"),
    ("6", "Configure (install method, install dir)"),
    ("7", "Verify & health-check installed tools"),
    ("8", "Help / glossary"),
    ("9", "Change familiarity level"),
    ("0", "Exit"),
]


def _menu_sep() -> str:
    return "·" if S.enabled else "-"


def menu_labels() -> list[str]:
    """Flat labels for the curses front-end."""
    sep = _menu_sep()
    return [f"{num} {sep} {label}" for num, label in MENU_ITEMS]


def print_main_menu(env, cfg, dry_run) -> None:
    clear_screen()
    sep = _menu_sep()
    sub = f"method={cfg['method']} {sep} familiarity={cfg['familiarity']}"
    if dry_run:
        sub += f" {sep} DRY-RUN"
    box(f"{APP_NAME} {APP_VERSION}", sub)
    if dry_run:
        print(S.magenta("  DRY-RUN: commands will be shown, never executed.\n"))
    sep = _menu_sep()
    for num, label in MENU_ITEMS:
        print(f"  {S.bold(num)} {sep} {label}")
    print()


def dispatch(choice, manifest, env, cfg, dry_run, level):
    """Run one menu action. Returns ('exit', None) or ('level', new_level) or None."""
    if choice == "1":
        action_quick_install(manifest, env, cfg, dry_run, level)
    elif choice == "2":
        action_browse_category(manifest, env, cfg, dry_run, level)
    elif choice == "3":
        action_pick_individual(manifest, env, cfg, dry_run, level)
    elif choice == "4":
        action_install_everything(manifest, env, cfg, dry_run, level)
    elif choice == "5":
        action_setup_fleet(env, cfg, dry_run, level)
    elif choice == "6":
        action_configure(env, cfg, level)
    elif choice == "7":
        action_health_check(manifest, env, level)
    elif choice == "8":
        action_help(level)
    elif choice == "9":
        return ("level", action_change_familiarity(cfg))
    elif choice == "0":
        return ("exit", None)
    return None


def run(manifest_path: str | None = None, dry_run: bool = False, use_curses: bool | None = None) -> int:
    """Entry point. Returns a process exit code (0 = clean)."""
    state = load_state()
    cfg = {
        "familiarity": state.get("familiarity"),
        "method": state.get("method"),
        "install_dir": state.get("install_dir", ""),
    }

    env = detect_environment()
    _valid_methods = {"pip", "pipx", "git", "docker"}
    if cfg["method"] not in _valid_methods:
        cfg["method"] = recommend_method(env)

    # STEP 0: familiarity (asked once, persisted).
    # Validate: must be an int in [1, 5]; anything else (corrupt state, wrong type)
    # triggers the prompt again so we never pass a bad value downstream.
    _fam = cfg["familiarity"]
    if not (isinstance(_fam, int) and 1 <= _fam <= 5):
        cfg["familiarity"] = None
    if cfg["familiarity"] is None:
        cfg["familiarity"] = prompt_familiarity()
        state["familiarity"] = cfg["familiarity"]
        save_state(state)
    level = cfg["familiarity"]

    mpath = discover_manifest(manifest_path)
    manifest = load_manifest(mpath)

    # One-time environment briefing on first run.
    if not state.get("seen_env"):
        clear_screen()
        print_environment(env, level)
        if mpath:
            print(S.dim(f"\n  Manifest: {mpath}  ({len(manifest['tools'])} tools)"))
        else:
            print(S.yellow("\n  No MANIFEST.json found — fleet setup, configure, and help\n"
                           "  still work; tool installs need a manifest (--manifest PATH)."))
        state["seen_env"] = True
        save_state(state)
        pause()

    want_curses = _curses_available() if use_curses is None else use_curses

    try:
        while True:
            if want_curses:
                idx = curses_main_menu(menu_labels())
                if idx == -2:           # curses failed -> permanent ANSI fallback
                    want_curses = False
                    continue
                if idx < 0:
                    break
                choice = MENU_ITEMS[idx][0]
            else:
                print_main_menu(env, cfg, dry_run)
                choice = ask("  Choose an option (0-9)")
                if choice is EOF:
                    break

            result = dispatch(choice, manifest, env, cfg, dry_run, level)
            if result and result[0] == "exit":
                break
            if result and result[0] == "level":
                level = result[1]

            # Persist any config the user changed.
            state.update({"method": cfg["method"], "install_dir": cfg.get("install_dir", ""),
                          "familiarity": cfg["familiarity"]})
            save_state(state)
    except (EOFError, KeyboardInterrupt):
        print()

    clear_screen()
    box("Goodbye", "re-run anytime: python cognis_setup.py")
    print(S.green("  Thanks for using the Cognis Setup Wizard."))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cognis_setup.py",
        description="The guided Cognis setup wizard (stdlib only).",
    )
    parser.add_argument(
        "--manifest",
        help="Path to MANIFEST.json (auto-discovered if omitted).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show every command but never execute it.",
    )
    parser.add_argument(
        "--no-curses",
        action="store_true",
        help="Force the ANSI numbered menu even where curses is available.",
    )
    args = parser.parse_args(argv)
    try:
        return run(
            manifest_path=args.manifest,
            dry_run=args.dry_run,
            use_curses=False if args.no_curses else None,
        )
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.", file=sys.stderr)
        return 130
    except Exception as exc:  # unexpected error — print cleanly, no traceback
        print(f"cognis_setup: unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
