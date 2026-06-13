# Cognis Digital · Suite Launcher

> One script. Takes you from "I have this zip" to "52 repos live under github.com/cognis-digital with all my code pushed."

---

## Usage — step by step

The Suite Launcher (`cognis-launcher.sh`) provisions, pushes, and releases the Cognis Neural Suite tool repos. It runs guided/interactive, but every step has a non-interactive subcommand.

1. **Install / first run** — bootstrap the environment with the guided wizard (stdlib + `gh`):

   ```bash
   ./setup.sh                       # macOS / Linux / Git-Bash / WSL
   # Windows PowerShell:  .\setup.ps1
   ```

2. **Verify the toolchain and authenticate GitHub:**

   ```bash
   bash launcher/cognis-launcher.sh setup
   bash launcher/cognis-launcher.sh auth
   ```

3. **Provision the repos** — create every repo and push its files, or jump into one tool's per-project menu:

   ```bash
   bash launcher/cognis-launcher.sh create-all
   bash launcher/cognis-launcher.sh hop promptmirror
   ```

4. **Read the state / verify** — snapshot status and run the cross-tool smoke test:

   ```bash
   bash launcher/cognis-launcher.sh status
   bash launcher/cognis-launcher.sh smoke
   ```

5. **Use it in automation** — cut a release across all repos non-interactively (great for CI):

   ```bash
   bash launcher/cognis-launcher.sh list
   bash launcher/cognis-launcher.sh release-all v0.1.0
   ```

## Quick start (guided)

**New here? Run one command and type a number.**

```bash
./setup.sh          # macOS / Linux / Git-Bash / WSL
```

```powershell
.\setup.ps1         # Windows PowerShell
```

That launches the **Cognis guided setup wizard** — a friendly, numbered menu
that explains everything at *your* level. It first asks how comfortable you are
with the terminal (1 = "barely touched one", 5 = "expert"), then adapts how much
it explains. No third-party packages required — it's pure Python standard
library, so it runs on a fresh machine.

```
How familiar are you with the terminal?   (1-5)

╔══════════════════════════════════════════════════════════════╗
║ Cognis Setup Wizard 1.0          method=pipx · familiarity=3   ║
╚══════════════════════════════════════════════════════════════╝

  1 · Quick install (recommended starter bundle)
  2 · Browse by category
  3 · Pick individual tools
  4 · Install everything
  5 · Set up the local AI fleet (--ai mode)
  6 · Configure (install method, install dir)
  7 · Verify & health-check installed tools
  8 · Help / glossary
  9 · Change familiarity level
  0 · Exit

  Choose an option (0-9):
```

Every action follows the same safe contract: **explain → show the EXACT command
→ confirm `[Y/n]` → run → report → back to the menu.** Nothing destructive runs
without your OK; add `--dry-run` to preview every command without executing it:

```bash
./setup.sh --dry-run
```

The wizard reads the canonical Cognis tool catalog — a local `MANIFEST.json` if
one is present, otherwise it fetches
[`cognis-arsenal/MANIFEST.json`](https://github.com/cognis-digital/cognis-arsenal)
from GitHub. With no catalog reachable (offline), it still runs: the AI-fleet
setup, configure, health-check and help all work.

You can also reach the wizard from the full launcher:

```bash
bash cognis-launcher.sh wizard      # same wizard
bash cognis-launcher.sh             # interactive menu → option "g"
```

> Prefer the full provisioning flow (create 52 GitHub repos, push, release)?
> That's below in **[Quick start (the happy path)](#quick-start-the-happy-path)**.

---

## What it does

`cognis-launcher.sh` is an interactive bash launcher that handles the full lifecycle:

1. **Environment setup** — checks for `git`, `gh`, `python3`, `pip`, `jq`, `fzf`; installs the `cognis-core` framework.
2. **GitHub CLI authentication** — guides you through `gh auth login` with the right scopes (`repo`, `workflow`, `admin:org`).
3. **Organization config** — saves your org name (default `cognis-digital`), visibility, branch.
4. **Bulk repo creation** — creates 52 GitHub repos with descriptions, topics, homepage, and disables wikis.
5. **File transfer** — `git init` → commit → set remote → push every one of the 52 tool directories.
6. **Interactive hop menu** — `fzf`-driven (or numbered fallback) menu to jump into any of the 52 projects.
7. **Per-project actions** — run scans, browse scenarios, open the repo on GitHub, create issues, cut releases.
8. **Bulk release** — tag + create GitHub releases across all 52 repos in one shot.

Everything is idempotent — re-running skips already-created repos. State persists in `~/.cognis-suite/state.env`.

---

## Quick start (the happy path)

From the suite root directory:

```bash
# 1. Run the launcher (interactive menu appears)
bash launcher/cognis-launcher.sh
```

The menu walks you through:

```
1)  Verify environment (git / gh / python / pip)
2)  GitHub authentication
3)  Configure (org, visibility, branch…)
4)  Create all 52 repos + push files
5)  Create / re-push a single repo
6)  Install all 52 tools locally (pip -e)
7)  Hop to a project (interactive)
8)  Show status of all 52 projects
9)  Run multi-scenario smoke test (~20s)
10) Tag & release all 52
```

The typical first-time flow is **1 → 2 → 3 → 4 → 7**.

---

## Non-interactive (CI / scripted) usage

Every menu action also works as a CLI subcommand:

```bash
# One-time setup
bash launcher/cognis-launcher.sh setup
bash launcher/cognis-launcher.sh auth

# Provision everything
bash launcher/cognis-launcher.sh create-all

# Jump straight to a tool's per-project menu
bash launcher/cognis-launcher.sh hop promptmirror

# Status snapshot
bash launcher/cognis-launcher.sh status

# Smoke test (runs every tool against every scenario)
bash launcher/cognis-launcher.sh smoke

# Release v0.1.0 on all 52 repos
bash launcher/cognis-launcher.sh release-all v0.1.0

# Just list the 52 slugs
bash launcher/cognis-launcher.sh list
```

---

## What gets created on GitHub

For each of the 52 tools, the launcher creates:

| Item | Value |
|---|---|
| Repo name | `cognis-digital/<slug>` (configurable owner) |
| Description | Set from the catalog (e.g. *"AI Agent Permission & Access Auditor…"*) |
| Homepage | `https://cognis.digital` |
| Topics | `cognis-digital`, `cognis-neural-suite`, `<domain>`, `<slug>` |
| Visibility | `public` (configurable) |
| Default branch | `main` |
| Initial commit | Contains the full tool tree (code, demos, tests, CI, Dockerfile, scenarios) |
| README | Generated per-repo, links back to the suite, lists demo scenarios |
| Wiki | Disabled (cleaner UX) |

Every repo also gets a generated **per-repo README** with:

- Install command (`pip install cognis-<slug>`)
- Quickstart for CLI + MCP server
- Auto-linked list of demo scenarios (with `SCENARIO.md` references)
- Cross-link back to the full Cognis Neural Suite

---

## Per-project hop menu

After picking a tool from the hop menu, you get an in-project sub-menu:

```
1)  Open shell in project directory
2)  Run `<slug> --help`
3)  Run smoke scan (root demo)
4)  Browse demo scenarios          ← reads SCENARIO.md, runs against pick
5)  Run pytest
6)  Open repo on GitHub (gh browse)
7)  Open an issue (gh issue create)
8)  Create a GitHub release
9)  Provision / re-push this repo
10) View README in less
11) pip install -e . (install this tool)
q)  Back to main menu
```

The scenario browser is especially useful — it shows each scenario's `SCENARIO.md` (the situation + expected findings) and offers to run the tool against that scenario inline.

---

## Configuration

Settings are stored in `~/.cognis-suite/state.env` and editable via menu option **3** or by editing the file:

```bash
GH_ORG="cognis-digital"          # owner (user or org)
GH_VISIBILITY="public"           # public | private | internal
GH_DEFAULT_BRANCH="main"
GH_USER="<auto-detected>"
PUSH_AFTER_CREATE="true"
DRY_RUN="false"                  # true = no GitHub calls, useful for testing
```

Set `DRY_RUN=true` to rehearse the whole flow without touching GitHub.

---

## Prerequisites

| Tool | macOS | Ubuntu / Debian | Fedora |
|---|---|---|---|
| `gh` | `brew install gh` | `sudo apt install gh` | `sudo dnf install gh` |
| `git` | `brew install git` | `sudo apt install git` | `sudo dnf install git` |
| `python3` | `brew install python` | `sudo apt install python3 python3-pip` | `sudo dnf install python3 python3-pip` |
| `jq` (optional) | `brew install jq` | `sudo apt install jq` | `sudo dnf install jq` |
| `fzf` (recommended) | `brew install fzf` | `sudo apt install fzf` | `sudo dnf install fzf` |

The launcher detects what's missing and prints the exact install command for your platform.

---

## Required GitHub scopes

When you authenticate, the launcher requests these scopes:

- `repo` — create repos, push commits, set descriptions
- `workflow` — push `.github/workflows/ci.yml` files
- `admin:org` — set topics on org-owned repos (skipped if owner = your user)

If you only want to push to your personal account, the `admin:org` scope is optional.

---

## Per-tool log files

Every repo provisioning writes to `~/.cognis-suite/logs/<slug>.log`. If a push fails, check that log first. Common issues:

- **403 / scope error** → re-run auth, ensure `repo` scope is included
- **Repo already exists** → launcher skips create, still pushes
- **`gh: command not found`** → run `bash launcher/cognis-launcher.sh setup`
- **Push rejected (non-fast-forward)** → the remote already has commits; either delete the repo or rebase

---

## Re-running safely

The launcher is idempotent:

- `create-all` skips repos that already exist on GitHub (only re-runs push)
- `git init` is no-op if the directory is already a git repo
- README is overwritten with the current generated version on every run
- Topics are re-applied on every run (additive)
- `release-all` skips releases that already exist for the same tag

You can stop with Ctrl-C and re-run; you'll pick up where you left off.

---

## Bulk release pattern

After the first wave of code is on GitHub, cut releases across all 52 at once:

```bash
bash launcher/cognis-launcher.sh release-all v0.1.0
```

This calls `gh release create v0.1.0 --generate-notes --title "<slug> v0.1.0"` on every repo that exists. Releases get auto-generated notes from commits.

---

## Custom org / personal use

To push to your personal account instead of `cognis-digital`:

```bash
# Menu option 3 → set GH_ORG to your username
# Or non-interactive:
echo 'GH_ORG="your-username"' >> ~/.cognis-suite/state.env
```

---

## Architecture

The launcher is one self-contained bash script (~700 lines). The catalog of 52 tools lives inline as a heredoc; each entry is `domain/slug:description`. The provisioning logic is a single function (`provision_one`) that handles git init → README render → repo create → topic set → push.

The per-project menu (`project_menu`) re-uses `gh` subcommands wherever possible — issues, releases, browse — so you stay in one shell context.
