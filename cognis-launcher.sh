#!/usr/bin/env bash
# ============================================================================
#  Cognis Digital Neural Suite — Launcher
#  ----------------------------------------------------------------------
#  Sets up environment, GitHub CLI, creates 52 repos, transfers files,
#  and provides an interactive project-hopping menu.
#
#  Usage:
#    ./setup.sh                             # GUIDED WIZARD — type a number
#    bash cognis-launcher.sh wizard         # same guided wizard
#    bash cognis-launcher.sh                # interactive menu
#    bash cognis-launcher.sh setup          # environment prerequisites only
#    bash cognis-launcher.sh auth           # GitHub auth only
#    bash cognis-launcher.sh create-all     # create all repos + push files
#    bash cognis-launcher.sh hop <slug>     # jump into a project shell
#    bash cognis-launcher.sh status         # status of all 52 projects
#    bash cognis-launcher.sh release-all v0.1.0  # tag/release all 52
# ============================================================================
set -u  # don't -e; we want to keep menu running on errors
IFS=$'\n\t'

# ----- paths & defaults -----------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TOOLS_DIR="$SUITE_ROOT/tools"
STATE_DIR="${COGNIS_STATE:-$HOME/.cognis-suite}"
STATE_FILE="$STATE_DIR/state.env"
LOG_DIR="$STATE_DIR/logs"
mkdir -p "$STATE_DIR" "$LOG_DIR"

# Defaults — only set if not already in env (env > state file > defaults)
: "${GH_ORG:=cognis-digital}"
: "${GH_VISIBILITY:=public}"        # public | private | internal
: "${GH_DEFAULT_BRANCH:=main}"
: "${GH_USER:=}"
: "${PUSH_AFTER_CREATE:=true}"
: "${DRY_RUN:=false}"

# Load saved state if any — but only for vars not already set in env
if [ -f "$STATE_FILE" ]; then
  # shellcheck disable=SC1090
  while IFS='=' read -r key val; do
    [[ "$key" =~ ^# ]] && continue
    [ -z "$key" ] && continue
    # only set if currently empty / unset in env
    val="${val%\"}"; val="${val#\"}"
    if [ -z "${!key:-}" ]; then
      eval "$key=\"\$val\""
    fi
  done < "$STATE_FILE"
fi

# ----- color & UI helpers ---------------------------------------------------
if [ -t 1 ]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'
  C_BLU=$'\033[34m'; C_MAG=$'\033[35m'; C_CYN=$'\033[36m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_MAG=""; C_CYN=""
fi

banner() {
  cat <<EOF
${C_CYN}${C_BOLD}
  ╔════════════════════════════════════════════════════════════════════╗
  ║                                                                    ║
  ║       Cognis Digital · Neural Suite Launcher                       ║
  ║       52 tools · GitHub provisioning · project hop menu            ║
  ║                                                                    ║
  ║       https://cognis.digital                                       ║
  ║                                                                    ║
  ╚════════════════════════════════════════════════════════════════════╝
${C_RESET}
EOF
}
hr()  { printf "${C_DIM}%s${C_RESET}\n" "────────────────────────────────────────────────────────────────────"; }
say() { printf "%s\n" "$*"; }
ok()  { printf "  ${C_GRN}✓${C_RESET} %s\n" "$*"; }
warn(){ printf "  ${C_YEL}!${C_RESET} %s\n" "$*"; }
err() { printf "  ${C_RED}✗${C_RESET} %s\n" "$*" >&2; }
ask() {
  local prompt="$1" default="${2-}"
  local reply
  if [ -n "$default" ]; then
    read -rp "  ${C_BOLD}?${C_RESET} $prompt [$default]: " reply
    reply="${reply:-$default}"
  else
    read -rp "  ${C_BOLD}?${C_RESET} $prompt: " reply
  fi
  printf "%s" "$reply"
}
confirm() {
  local prompt="$1" default="${2:-N}"
  local reply
  read -rp "  ${C_BOLD}?${C_RESET} $prompt (y/N): " reply
  reply="${reply:-$default}"
  [[ "$reply" =~ ^[Yy]([Ee][Ss])?$ ]]
}

save_state() {
  cat > "$STATE_FILE" <<EOF
# Cognis launcher state — auto-saved
GH_ORG="$GH_ORG"
GH_VISIBILITY="$GH_VISIBILITY"
GH_DEFAULT_BRANCH="$GH_DEFAULT_BRANCH"
GH_USER="$GH_USER"
PUSH_AFTER_CREATE="$PUSH_AFTER_CREATE"
DRY_RUN="$DRY_RUN"
EOF
}

# ----- tool catalog ---------------------------------------------------------
# Format: domain/slug:Description used as repo description
read -r -d '' CATALOG <<'CAT' || true
ai-security/aegis:AI Agent Permission & Access Auditor — surfaces the lethal trifecta of credentials + injection + reach
ai-security/promptmirror:Prompt-injection & indirect-injection scanner for any LLM context input
ai-security/ledgermind:Local LLM cost & token forensics proxy with anomaly detection
ai-security/adversa:LLM red-team harness — OWASP LLM Top 10 + MITRE ATLAS attack packs
ai-security/guardpost:Runtime agent firewall — PII redaction, rate limits, policy enforcement
ai-security/hallumark:LLM hallucination & grounding auditor for RAG systems
ai-security/aicard:Auto-generated NIST AI RMF / EU AI Act Annex IV model & system cards
ai-security/biascope:Embedded bias probe suite — demographic / occupational / geographic
ai-security/mcpharden:MCP server hardening linter — capability declarations, transport, tool descriptions
ai-security/agentlog:Agentic workflow replay & audit with OTel GenAI semantic conventions
ai-security/ragshield:RAG corpus poisoning detector — embedding anomalies, backdoor triggers
blue-team/sentrylog:Single-file SIEM for small teams — Sigma rules + multi-source ingest
blue-team/edrgap:EDR coverage & bypass detector — reconciles MDM + EDR + AD inventories
blue-team/canarynet:Self-hosted canary token network — AWS keys, DNS, docs, web URLs
blue-team/phishforge:Open-source phishing simulation — campaigns, templates, training
blue-team/sbomgate:Continuous SBOM diff & vulnerability watch with maintainer-change tracking
blue-team/honeytrace:Active-decoy network lure system — SSH, RDP, SMB, web honeypots
red-team/c2detect:C2 server fingerprinter — Cobalt Strike, Sliver, Mythic, Havoc, Brute Ratel
red-team/payloadlab:Static malicious payload analyzer — PE/ELF/LNK/macro/OneNote
red-team/redpath:Active Directory attack path mapper — minimum-cost paths + remediation priority
red-team/pwnreview:Pentest report generator — YAML findings to CREST-grade PDF
red-team/crackq:Self-hosted password cracking queue — multi-user hashcat with audit log
osint/personagraph:Identity resolution dossier — username/email/phone cross-platform
osint/maritimeint:AIS vessel tracking & sanctions-evasion anomaly detection
osint/geolens:Image geolocation toolkit — EXIF, sun-shadow, OCR, reverse-search
osint/corpmap:Corporate structure & beneficial-ownership mapper
osint/cryptotrace:Free-tier blockchain investigator — ETH/BTC clustering + sanctions xref
osint/darkmirror:Surface-web mirror of public Tor leak-site index for brand monitoring
federal/checkpoint-ai:NIST AI RMF / EU AI Act / ISO 42001 self-assessment & SSP generator
federal/cmmcmap:CMMC Level 2 practice mapper — stack-aware SSP skeleton generator
federal/fedramplens:FedRAMP boundary visualizer & OSCAL-format SSP/POAM generator
federal/sbirscout:SBIR/STTR topic discovery — DSIP + SBIR.gov + NIH digest with bid scoring
federal/gsafinder:GSA Schedule opportunity surveyor — SAM.gov + eBuy + FedConnect
federal/clearancepath:Personnel clearance hygiene tracker — SF-86, SEAD-3/4, training currency
privacy/recall:Privacy-first local RAG over personal data — encrypted, audit-logged
privacy/optout:Automated data-broker opt-out engine — top 50 brokers, CCPA/GDPR letters
privacy/vaultmap:Personal asset & account inventory — estate-planning-grade encrypted
privacy/breachwatch:Personal breach aggregator — HIBP + DeHashed + stealer-log triage
privacy/piicomb:Local PII discovery in your own files — SSN/CC/passport/DL/email/phone/DOB
privacy/trackblock:Family phone stalkerware audit — MVT-class iOS/Android forensics
privacy/privacyshell:Hardened browser profile generator — Firefox / LibreWolf / Brave
network/dnsaudit:DNS posture & misconfiguration scanner — SPF/DKIM/DMARC/DNSSEC/CAA
network/certpatrol:TLS cert lifecycle & rogue-issuance watch via Certificate Transparency
network/egresswatch:Server-side outbound connection auditor — eBPF/Falco wrapper
info-integrity/claimtrace:Misinformation provenance tracer — earliest-known appearance graph
info-integrity/deepcheck:Lightweight synthetic-media detector with C2PA validation
info-integrity/electionlens:Influence-operations pattern monitor for election periods
info-integrity/narrativediff:News bias & framing diff across 50+ outlets per event
dev-supply-chain/depgraph:Dependency risk visualizer — Scorecard + OSV + typosquat + maintainer signals
dev-supply-chain/secretsweep:Repo secret scanner + auto-rotator across providers
dev-supply-chain/pipewatch-pro:CI/CD supply-chain auditor — GH Actions / GitLab CI / OWASP CI/CD Top 10
dev-supply-chain/ossaudit:OSS license compliance auditor — AGPL contamination + NOTICE generation
CAT

# Helpers to iterate catalog
each_tool() {
  # Echoes "domain slug description" lines
  printf "%s\n" "$CATALOG" | awk -F: '
    NF >= 2 {
      split($1, p, "/");
      desc=$2; for (i=3;i<=NF;i++) desc=desc":"$i;
      printf "%s %s %s\n", p[1], p[2], desc
    }'
}
tool_count() { each_tool | wc -l | tr -d ' '; }
slug_to_domain() {
  local slug="$1"
  each_tool | awk -v s="$slug" '$2==s {print $1; exit}'
}
slug_to_desc() {
  local slug="$1"
  each_tool | awk -v s="$slug" '
    $2==s { for(i=3;i<=NF;i++) printf "%s%s", $i, (i<NF?" ":""); print ""; exit }'
}
slug_to_path() {
  local slug="$1"
  local dom; dom="$(slug_to_domain "$slug")"
  [ -z "$dom" ] && return 1
  printf "%s/%s/%s" "$TOOLS_DIR" "$dom" "$slug"
}
slug_topics() {
  local slug="$1"
  local dom; dom="$(slug_to_domain "$slug")"
  printf "cognis-digital,cognis-neural-suite,%s,%s" "$dom" "$slug"
}

# ----- ===  Section 1: Environment setup  =================================
cmd_setup() {
  banner
  hr; say "${C_BOLD}Step 1 — Verify environment${C_RESET}"; hr
  local missing=()

  if command -v git >/dev/null 2>&1; then
    ok "git $(git --version | awk '{print $3}')"
  else missing+=("git"); fi

  if command -v gh >/dev/null 2>&1; then
    ok "gh $(gh --version | head -1 | awk '{print $3}')"
  else missing+=("gh"); fi

  if command -v python3 >/dev/null 2>&1; then
    ok "python $(python3 --version | awk '{print $2}')"
  else missing+=("python3"); fi

  if command -v pip >/dev/null 2>&1 || command -v pip3 >/dev/null 2>&1; then
    ok "pip $(pip3 --version 2>/dev/null | awk '{print $2}')"
  else missing+=("pip"); fi

  if command -v jq >/dev/null 2>&1; then ok "jq $(jq --version)"; else missing+=("jq (optional)"); fi
  if command -v fzf >/dev/null 2>&1; then ok "fzf $(fzf --version | awk '{print $1}')"; else warn "fzf not found (optional — improves hop menu)"; fi

  if [ ${#missing[@]} -gt 0 ]; then
    err "Missing prerequisites: ${missing[*]}"
    say
    say "  Install on macOS:   brew install gh git python jq fzf"
    say "  Install on Ubuntu:  sudo apt update && sudo apt install -y gh git python3 python3-pip jq fzf"
    say "  Install on Fedora:  sudo dnf install -y gh git python3 python3-pip jq fzf"
    return 1
  fi

  hr; say "${C_BOLD}Step 2 — Install Python framework${C_RESET}"; hr
  if python3 -c "import cognis_core" 2>/dev/null; then
    ok "cognis_core already importable"
  else
    say "  Installing cognis-core (the shared framework)…"
    ( cd "$TOOLS_DIR/_shared" && pip install -e . --quiet ) && ok "cognis-core installed" || { err "cognis-core install failed"; return 1; }
  fi

  hr; say "${C_BOLD}Step 3 — Optional: install all 52 tools locally${C_RESET}"; hr
  if confirm "Install all 52 tools in editable mode now? (~3 min)"; then
    bash "$TOOLS_DIR/_shared/install_all.sh"
  else
    warn "Skipped. You can run this later via menu → option 6."
  fi

  ok "Environment ready."
  return 0
}

# ----- ===  Section 2: GitHub auth  =======================================
cmd_auth() {
  banner
  hr; say "${C_BOLD}GitHub CLI authentication${C_RESET}"; hr

  if ! command -v gh >/dev/null 2>&1; then
    err "gh CLI not installed. Run: ${C_BOLD}cognis-launcher.sh setup${C_RESET}"
    return 1
  fi

  if gh auth status >/dev/null 2>&1; then
    GH_USER=$(gh api user --jq .login 2>/dev/null || echo "unknown")
    ok "Already authenticated as ${C_BOLD}$GH_USER${C_RESET}"
    if confirm "Re-authenticate (switch account, refresh scopes)?"; then
      gh auth logout 2>/dev/null
    else
      save_state; return 0
    fi
  fi

  say "  Choose authentication method:"
  say "    ${C_BOLD}1${C_RESET}) Web browser (recommended for new users)"
  say "    ${C_BOLD}2${C_RESET}) Paste a Personal Access Token"
  say "    ${C_BOLD}3${C_RESET}) Use existing SSH key + gh auth login"
  local method; method="$(ask "Selection" "1")"

  # Required scopes: repo (create/push), workflow (Actions), admin:org (set topics on org repos)
  local SCOPES="repo,workflow,admin:org"
  case "$method" in
    1) gh auth login --hostname github.com --git-protocol https --web --scopes "$SCOPES" ;;
    2)
      say "  Create a token at: https://github.com/settings/tokens/new?scopes=repo,workflow,admin:org"
      say "  Then paste it below."
      gh auth login --hostname github.com --git-protocol https --with-token
      ;;
    3) gh auth login --hostname github.com --git-protocol ssh --web --scopes "$SCOPES" ;;
    *) err "Invalid selection"; return 1 ;;
  esac

  if gh auth status >/dev/null 2>&1; then
    GH_USER=$(gh api user --jq .login 2>/dev/null)
    ok "Authenticated as ${C_BOLD}$GH_USER${C_RESET}"

    # Configure git protocol to match
    gh auth setup-git 2>/dev/null && ok "Git credentials configured for gh"

    # Ask about org
    say
    say "  ${C_BOLD}Owner for the 52 repos:${C_RESET}"
    say "    Personal account: $GH_USER"
    say "    Organization:     cognis-digital (or other)"
    GH_ORG="$(ask "Target owner (user or org)" "$GH_ORG")"

    # Verify org access if not personal
    if [ "$GH_ORG" != "$GH_USER" ]; then
      if gh api "orgs/$GH_ORG" >/dev/null 2>&1; then
        ok "Organization ${C_BOLD}$GH_ORG${C_RESET} accessible"
      else
        warn "Cannot access org $GH_ORG — does it exist? Do you have admin:org scope?"
        if confirm "Create the organization now (requires browser)?"; then
          gh browse "https://github.com/account/organizations/new"
          say "  Once created, press enter to continue."
          read -r _
        fi
      fi
    fi

    say
    GH_VISIBILITY="$(ask "Default repo visibility (public|private|internal)" "$GH_VISIBILITY")"
    save_state
    ok "Auth complete. Settings saved to $STATE_FILE"
    return 0
  else
    err "Authentication failed"
    return 1
  fi
}

# ----- ===  Section 3: Repo creation + file transfer  =====================

# Render a per-repo README that points back at the suite + includes scenarios
render_repo_readme() {
  local slug="$1" desc="$2" domain="$3" path="$4"
  local scenarios=()
  if [ -d "$path/demos" ]; then
    while IFS= read -r d; do scenarios+=("$d"); done < <(find "$path/demos" -mindepth 1 -maxdepth 1 -type d -name "[0-9]*" | sort)
  fi
  local scen_md=""
  if [ ${#scenarios[@]} -gt 0 ]; then
    scen_md+=$'\n## Built-in demo scenarios\n\nEvery scenario folder includes a `SCENARIO.md` describing what it represents and what findings to expect.\n\n'
    for s in "${scenarios[@]}"; do
      local sname; sname="$(basename "$s")"
      scen_md+="- \`demos/$sname/\` — see [\`SCENARIO.md\`](demos/$sname/SCENARIO.md)"$'\n'
    done
  fi

  cat > "$path/README.md" <<RDM
# ${slug^^} — ${desc}

> Part of the **[Cognis Neural Suite](https://github.com/${GH_ORG})** by [Cognis Digital](https://cognis.digital)
> MIT License · domain: \`${domain}\`

[![PyPI](https://img.shields.io/pypi/v/cognis-${slug}.svg)](https://pypi.org/project/cognis-${slug}/)
[![CI](https://github.com/${GH_ORG}/${slug}/actions/workflows/ci.yml/badge.svg)](https://github.com/${GH_ORG}/${slug}/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

${desc}.

## Install

\`\`\`bash
pip install cognis-${slug}
\`\`\`

For local development from this repo:

\`\`\`bash
pip install -e .
\`\`\`

## Quick start

\`\`\`bash
${slug} --version
${slug} scan demos/                          # run against bundled demo
${slug} scan demos/ --format sarif --out r.sarif --fail-on high
${slug} mcp                                   # start as MCP server (Cognis.Studio / Claude Desktop / Cursor)
\`\`\`
${scen_md}
## How it fits the Cognis Neural Suite

This tool is one of 52 in the [Cognis Neural Suite](https://github.com/${GH_ORG}). The full suite + launcher lives at:

- Suite landing: https://cognis.digital
- All 52 repos: https://github.com/${GH_ORG}
- Cognis.Studio (Enterprise AI Workforce, MCP host): https://cognis.studio

Every Suite tool ships an MCP server, so Cognis.Studio agents can call them as scoped capabilities.

## License

MIT. See [LICENSE](LICENSE).

## About

**[Cognis Digital](https://cognis.digital)** — Wyoming, USA · *Making Tomorrow Better Today: Advanced Cybersecurity, AI Innovation, and Blockchain Expertise.*
RDM
}

# Initialize one repo locally + create on GitHub + push
provision_one() {
  local slug="$1"
  local domain desc path
  domain="$(slug_to_domain "$slug")" || { err "Unknown slug: $slug"; return 1; }
  desc="$(slug_to_desc "$slug")"
  path="$TOOLS_DIR/$domain/$slug"
  [ ! -d "$path" ] && { err "Path missing: $path"; return 1; }

  local logf="$LOG_DIR/${slug}.log"
  : > "$logf"

  # --- 1. local git init -------------------------------------------------
  ( cd "$path"
    if [ ! -d .git ]; then
      git init -q --initial-branch="$GH_DEFAULT_BRANCH"
    else
      git symbolic-ref HEAD "refs/heads/$GH_DEFAULT_BRANCH" 2>/dev/null || true
    fi

    # Ensure .gitignore
    if [ ! -f .gitignore ]; then
      cat > .gitignore <<'GI'
__pycache__/
*.pyc
*.egg-info/
.venv/
dist/
build/
.pytest_cache/
*.html
!demos/**/*.html
.DS_Store
GI
    fi

    # Render a real per-repo README
    render_repo_readme "$slug" "$desc" "$domain" "$path"

    git add -A
    git -c user.name="Cognis Bot" -c user.email="bot@cognis.digital" \
        commit -q -m "Initial commit: $slug v0.1.0

Part of the Cognis Neural Suite (52 tools).
Domain: $domain
Description: $desc

https://cognis.digital" >> "$logf" 2>&1 || true
  )

  # --- 2. create on GitHub ----------------------------------------------
  local target="$GH_ORG/$slug"
  if gh repo view "$target" >/dev/null 2>&1; then
    warn "Repo already exists: $target — skipping create"
  else
    if [ "$DRY_RUN" = "true" ]; then
      ok "[dry-run] would create $target ($GH_VISIBILITY)"
    else
      gh repo create "$target" \
        --"$GH_VISIBILITY" \
        --description "$desc" \
        --homepage "https://cognis.digital" \
        --disable-wiki \
        >> "$logf" 2>&1 \
        && ok "created $target"
    fi
  fi

  # --- 3. set topics -----------------------------------------------------
  if [ "$DRY_RUN" != "true" ] && gh repo view "$target" >/dev/null 2>&1; then
    local topics; topics="$(slug_topics "$slug")"
    # gh repo edit accepts comma-separated topics
    gh repo edit "$target" --add-topic "$topics" >> "$logf" 2>&1 || true
  fi

  # --- 4. set remote + push ---------------------------------------------
  if [ "$PUSH_AFTER_CREATE" = "true" ] && [ "$DRY_RUN" != "true" ]; then
    ( cd "$path"
      if git remote | grep -q "^origin$"; then
        git remote set-url origin "https://github.com/$target.git"
      else
        git remote add origin "https://github.com/$target.git"
      fi
      git push -u origin "$GH_DEFAULT_BRANCH" >> "$logf" 2>&1 \
        && ok "pushed $target" \
        || warn "push failed for $target (see $logf)"
    )
  fi
}

cmd_create_all() {
  banner
  hr; say "${C_BOLD}Bulk repo creation — $(tool_count) tools → github.com/$GH_ORG/${C_RESET}"; hr
  if [ "$DRY_RUN" != "true" ] && ! gh auth status >/dev/null 2>&1; then
    err "Not authenticated. Run: ${C_BOLD}cognis-launcher.sh auth${C_RESET}"
    say "  (or set DRY_RUN=true to rehearse without GitHub)"
    return 1
  fi

  say "  Owner:       ${C_BOLD}$GH_ORG${C_RESET}"
  say "  Visibility:  ${C_BOLD}$GH_VISIBILITY${C_RESET}"
  say "  Branch:      ${C_BOLD}$GH_DEFAULT_BRANCH${C_RESET}"
  say "  Push files:  ${C_BOLD}$PUSH_AFTER_CREATE${C_RESET}"
  say "  Dry run:     ${C_BOLD}$DRY_RUN${C_RESET}"
  say
  if ! confirm "Proceed with creating $(tool_count) repos under $GH_ORG?"; then
    warn "Aborted."
    return 0
  fi

  local n=0 total; total=$(tool_count)
  while IFS=' ' read -r domain slug rest; do
    n=$((n + 1))
    printf "${C_DIM}[%2d/%d]${C_RESET} %s/${C_BOLD}%s${C_RESET}\n" "$n" "$total" "$domain" "$slug"
    provision_one "$slug"
  done < <(each_tool)

  hr
  ok "Done. Visit https://github.com/$GH_ORG"
  say "  Per-repo logs in $LOG_DIR"
}

cmd_create_one() {
  local slug="$1"
  if [ -z "$slug" ]; then
    err "Usage: cognis-launcher.sh create <slug>"
    say "  Run 'cognis-launcher.sh list' to see all slugs."
    return 1
  fi
  banner
  hr; say "Creating single repo: ${C_BOLD}$slug${C_RESET}"; hr
  if [ "$DRY_RUN" != "true" ] && ! gh auth status >/dev/null 2>&1; then
    err "Not authenticated. Run: ${C_BOLD}cognis-launcher.sh auth${C_RESET}"
    say "  (or set DRY_RUN=true to rehearse without GitHub)"
    return 1
  fi
  provision_one "$slug"
}

# ----- ===  Section 4: Status / health  ===================================
cmd_status() {
  banner
  hr; say "${C_BOLD}Project status — $(tool_count) tools${C_RESET}"; hr

  local authed="no"
  if gh auth status >/dev/null 2>&1; then
    authed="yes ($GH_USER)"
  fi
  say "  ${C_BOLD}Auth:${C_RESET}    $authed"
  say "  ${C_BOLD}Org:${C_RESET}     $GH_ORG"
  say "  ${C_BOLD}Visibility:${C_RESET}  $GH_VISIBILITY"
  say "  ${C_BOLD}State file:${C_RESET}  $STATE_FILE"
  hr

  printf "  ${C_BOLD}%-25s %-18s %-8s %-8s %-12s${C_RESET}\n" "TOOL" "DOMAIN" "LOCAL" "REMOTE" "INSTALLED"
  printf "  ${C_DIM}%s${C_RESET}\n" "─────────────────────────────────────────────────────────────────────────────"

  while IFS=' ' read -r domain slug rest; do
    local path="$TOOLS_DIR/$domain/$slug"
    local has_git="no" has_remote="no" installed="no"
    [ -d "$path/.git" ] && has_git="${C_GRN}yes${C_RESET}"
    if [ "$authed" != "no" ] && gh repo view "$GH_ORG/$slug" >/dev/null 2>&1; then
      has_remote="${C_GRN}yes${C_RESET}"
    fi
    if command -v "$slug" >/dev/null 2>&1; then
      installed="${C_GRN}yes${C_RESET}"
    fi
    printf "  %-25s %-18s %-8b %-8b %-12b\n" "$slug" "$domain" "$has_git" "$has_remote" "$installed"
  done < <(each_tool)
  hr
}

# ----- ===  Section 5: Smoke / health  ====================================
cmd_smoke() {
  banner
  hr; say "Running multi-scenario smoke test (~20 sec)…"; hr
  bash "$TOOLS_DIR/_shared/smoke_test_scenarios.sh" | tee "$LOG_DIR/smoke-$(date +%s).log"
}

cmd_install_local() {
  banner
  hr; say "Installing 52 tools in editable mode (~3 min)…"; hr
  bash "$TOOLS_DIR/_shared/install_all.sh"
}

# Launch the canonical Cognis guided SETUP WIZARD (stdlib-only Python).
# Numbered, familiarity-adaptive menu — type a number, it explains + confirms.
# Delegates to the setup.sh bootstrap (manifest discovery/fetch + fallback).
cmd_wizard() {
  local boot="$SCRIPT_DIR/setup.sh"
  if [ -x "$boot" ] || [ -f "$boot" ]; then
    bash "$boot" "$@"
    return $?
  fi
  # Fallback: call the wizard directly if the bootstrap is missing.
  local py=""
  for c in python3 python py; do command -v "$c" >/dev/null 2>&1 && { py="$c"; break; }; done
  [ -n "$py" ] || { err "Need Python 3 for the setup wizard"; return 1; }
  "$py" "$SCRIPT_DIR/cognis_setup.py" "$@"
}

# ----- ===  Section 6: Per-project actions  ===============================
project_menu() {
  local slug="$1"
  local domain path desc
  domain="$(slug_to_domain "$slug")" || { err "Unknown: $slug"; return 1; }
  path="$(slug_to_path "$slug")"
  desc="$(slug_to_desc "$slug")"

  while true; do
    clear 2>/dev/null || printf "\033c"
    banner
    hr
    printf "  ${C_BOLD}Project:${C_RESET} %s   ${C_DIM}(%s)${C_RESET}\n" "$slug" "$domain"
    printf "  ${C_DIM}%s${C_RESET}\n" "$desc"
    printf "  ${C_DIM}Path:${C_RESET} %s\n" "$path"
    hr
    cat <<EOM
    ${C_BOLD}1)${C_RESET}  Open shell in project directory
    ${C_BOLD}2)${C_RESET}  Run \`$slug --help\`
    ${C_BOLD}3)${C_RESET}  Run smoke scan (root demo)
    ${C_BOLD}4)${C_RESET}  Browse demo scenarios
    ${C_BOLD}5)${C_RESET}  Run pytest
    ${C_BOLD}6)${C_RESET}  Open repo on GitHub (gh browse)
    ${C_BOLD}7)${C_RESET}  Open an issue (gh issue create)
    ${C_BOLD}8)${C_RESET}  Create a GitHub release
    ${C_BOLD}9)${C_RESET}  Provision / re-push this repo to github.com/$GH_ORG/$slug
    ${C_BOLD}10)${C_RESET} View README in less
    ${C_BOLD}11)${C_RESET} pip install -e .  (install this tool)
    ${C_BOLD}q)${C_RESET}  Back to main menu
EOM
    local choice; choice="$(ask "Action" "")"
    case "$choice" in
      1) ( cd "$path" && "${SHELL:-bash}" ) ;;
      2) ( cd "$path" && "$slug" --help 2>&1 | less -R ) ;;
      3) ( cd "$path" && "$slug" scan demos/ 2>&1 | less -R ) ;;
      4) browse_scenarios "$slug" ;;
      5) ( cd "$path" && pytest -q 2>&1 | less -R ) ;;
      6) gh repo view "$GH_ORG/$slug" --web 2>/dev/null || gh browse --repo "$GH_ORG/$slug" ;;
      7) ( cd "$path" && gh issue create --repo "$GH_ORG/$slug" ) ;;
      8)
         local tag; tag="$(ask "Release tag (e.g. v0.1.0)" "v0.1.0")"
         ( cd "$path" && gh release create "$tag" --repo "$GH_ORG/$slug" --generate-notes )
         ;;
      9) provision_one "$slug"; read -rp "Press Enter…" _ ;;
      10) less "$path/README.md" 2>/dev/null || warn "no README" ;;
      11) ( cd "$path" && pip install -e . && read -rp "Press Enter…" _ ) ;;
      q|Q|"") return 0 ;;
      *) warn "Unknown choice: $choice"; sleep 1 ;;
    esac
  done
}

browse_scenarios() {
  local slug="$1"
  local path; path="$(slug_to_path "$slug")"
  local scenarios=()
  while IFS= read -r d; do scenarios+=("$d"); done < <(find "$path/demos" -mindepth 1 -maxdepth 1 -type d -name "[0-9]*" | sort)
  if [ ${#scenarios[@]} -eq 0 ]; then
    warn "No structured scenarios for $slug — only root demo."
    ( cd "$path" && ls demos/ )
    read -rp "Press Enter…" _; return
  fi
  while true; do
    clear 2>/dev/null; banner; hr
    printf "  ${C_BOLD}Scenarios for %s${C_RESET}\n" "$slug"; hr
    local i=1
    for s in "${scenarios[@]}"; do
      printf "    ${C_BOLD}%d)${C_RESET}  %s\n" "$i" "$(basename "$s")"
      i=$((i + 1))
    done
    printf "    ${C_BOLD}q)${C_RESET}  Back\n"
    local choice; choice="$(ask "Pick scenario" "")"
    [[ "$choice" =~ ^[Qq]$|^$ ]] && return
    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#scenarios[@]}" ]; then
      local target="${scenarios[$((choice-1))]}"
      clear 2>/dev/null; banner; hr
      printf "  ${C_BOLD}%s${C_RESET}\n\n" "$(basename "$target")"
      if [ -f "$target/SCENARIO.md" ]; then
        cat "$target/SCENARIO.md"
      fi
      hr
      say "  Run against this scenario:"
      say "    ${C_DIM}cd $path && $slug scan demos/$(basename "$target")/${C_RESET}"
      say
      if confirm "Run now?" "Y"; then
        ( cd "$path" && "$slug" scan "demos/$(basename "$target")/" 2>&1 | less -R )
      fi
    fi
  done
}

# ----- ===  Section 7: Hop menu  ==========================================
hop_menu() {
  if command -v fzf >/dev/null 2>&1; then
    local pick
    pick=$(each_tool | awk '{
        slug=$2; dom=$1;
        desc=""; for(i=3;i<=NF;i++) desc=desc" "$i;
        printf "%-22s  %-18s %s\n", slug, dom, desc
      }' | fzf --prompt="Pick a tool: " --height=80% --reverse --border --header="$(tool_count) tools · ↑↓ to navigate · ↵ to select")
    [ -z "$pick" ] && return
    local slug; slug=$(echo "$pick" | awk '{print $1}')
    project_menu "$slug"
  else
    # Plain numbered menu, paginated by domain
    while true; do
      clear 2>/dev/null; banner; hr
      say "  ${C_BOLD}Choose a domain${C_RESET}"; hr
      local domains=(ai-security blue-team red-team osint federal privacy network info-integrity dev-supply-chain)
      local i=1
      for d in "${domains[@]}"; do
        local n; n=$(each_tool | awk -v dom="$d" '$1==dom' | wc -l | tr -d ' ')
        printf "    ${C_BOLD}%d)${C_RESET} %-22s (%s tools)\n" "$i" "$d" "$n"
        i=$((i+1))
      done
      printf "    ${C_BOLD}q)${C_RESET} Back\n"
      local choice; choice="$(ask "Domain" "")"
      [[ "$choice" =~ ^[Qq]$|^$ ]] && return
      if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#domains[@]}" ]; then
        domain_menu "${domains[$((choice-1))]}"
      fi
    done
  fi
}

domain_menu() {
  local dom="$1"
  while true; do
    clear 2>/dev/null; banner; hr
    say "  ${C_BOLD}Domain:${C_RESET} $dom"; hr
    local slugs=()
    while IFS=' ' read -r d s rest; do slugs+=("$s"); done < <(each_tool | awk -v dom="$dom" '$1==dom')
    local i=1
    for s in "${slugs[@]}"; do
      printf "    ${C_BOLD}%2d)${C_RESET} %-22s — %s\n" "$i" "$s" "$(slug_to_desc "$s")"
      i=$((i+1))
    done
    printf "    ${C_BOLD}q)${C_RESET}  Back\n"
    local choice; choice="$(ask "Tool" "")"
    [[ "$choice" =~ ^[Qq]$|^$ ]] && return
    if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#slugs[@]}" ]; then
      project_menu "${slugs[$((choice-1))]}"
    fi
  done
}

# ----- ===  Section 8: Bulk release  ======================================
cmd_release_all() {
  local tag="${1:-v0.1.0}"
  banner
  hr; say "Tagging $tag across all 52 repos…"; hr
  if ! gh auth status >/dev/null 2>&1; then err "Not authenticated."; return 1; fi
  if ! confirm "Create release $tag for every existing $GH_ORG repo?"; then return 0; fi
  while IFS=' ' read -r domain slug rest; do
    if gh repo view "$GH_ORG/$slug" >/dev/null 2>&1; then
      gh release create "$tag" --repo "$GH_ORG/$slug" --generate-notes \
        --title "$slug $tag" >/dev/null 2>&1 \
        && ok "released $slug $tag" \
        || warn "release skipped (already exists?) for $slug"
    fi
  done < <(each_tool)
}

# ----- ===  Section 9: Config edit  =======================================
cmd_config() {
  while true; do
    clear 2>/dev/null; banner; hr
    say "${C_BOLD}Configuration${C_RESET}"; hr
    printf "    ${C_BOLD}1)${C_RESET} Org / owner:        %s\n"  "$GH_ORG"
    printf "    ${C_BOLD}2)${C_RESET} Default visibility: %s\n"  "$GH_VISIBILITY"
    printf "    ${C_BOLD}3)${C_RESET} Default branch:     %s\n"  "$GH_DEFAULT_BRANCH"
    printf "    ${C_BOLD}4)${C_RESET} Push after create:  %s\n"  "$PUSH_AFTER_CREATE"
    printf "    ${C_BOLD}5)${C_RESET} Dry run mode:       %s\n"  "$DRY_RUN"
    printf "    ${C_BOLD}q)${C_RESET} Back\n"
    local choice; choice="$(ask "Edit" "")"
    case "$choice" in
      1) GH_ORG="$(ask "Org / owner" "$GH_ORG")" ;;
      2) GH_VISIBILITY="$(ask "Visibility (public|private|internal)" "$GH_VISIBILITY")" ;;
      3) GH_DEFAULT_BRANCH="$(ask "Branch" "$GH_DEFAULT_BRANCH")" ;;
      4) PUSH_AFTER_CREATE="$(ask "Push after create (true|false)" "$PUSH_AFTER_CREATE")" ;;
      5) DRY_RUN="$(ask "Dry run (true|false)" "$DRY_RUN")" ;;
      q|Q|"") save_state; return ;;
      *) warn "?" ;;
    esac
    save_state
  done
}

# ----- ===  Main menu  ====================================================
main_menu() {
  while true; do
    clear 2>/dev/null; banner
    local authed="${C_RED}not authenticated${C_RESET}"
    gh auth status >/dev/null 2>&1 && authed="${C_GRN}auth ✓${C_RESET} ${C_DIM}($GH_USER)${C_RESET}"
    printf "  ${C_BOLD}Org:${C_RESET} %s    ${C_BOLD}Status:${C_RESET} %b\n" "$GH_ORG" "$authed"
    hr
    cat <<EOM
    ${C_BOLD}=== Start here ===${C_RESET}
      ${C_BOLD}g)${C_RESET}  ${C_GRN}Guided setup wizard${C_RESET} (numbered, explains everything)

    ${C_BOLD}=== Setup ===${C_RESET}
      ${C_BOLD}1)${C_RESET}  Verify environment (git / gh / python / pip)
      ${C_BOLD}2)${C_RESET}  GitHub authentication
      ${C_BOLD}3)${C_RESET}  Configure (org, visibility, branch…)

    ${C_BOLD}=== Provision ===${C_RESET}
      ${C_BOLD}4)${C_RESET}  Create all 52 repos + push files
      ${C_BOLD}5)${C_RESET}  Create / re-push a single repo
      ${C_BOLD}6)${C_RESET}  Install all 52 tools locally (pip -e)

    ${C_BOLD}=== Use ===${C_RESET}
      ${C_BOLD}7)${C_RESET}  Hop to a project (interactive)
      ${C_BOLD}8)${C_RESET}  Show status of all 52 projects
      ${C_BOLD}9)${C_RESET}  Run multi-scenario smoke test (~20s)

    ${C_BOLD}=== Bulk ===${C_RESET}
      ${C_BOLD}10)${C_RESET} Tag & release all 52 (gh release create)

      ${C_BOLD}q)${C_RESET}  Quit
EOM
    local choice; choice="$(ask "Action" "")"
    case "$choice" in
      g|G) cmd_wizard; read -rp "Press Enter…" _ ;;
      1) cmd_setup; read -rp "Press Enter…" _ ;;
      2) cmd_auth;  read -rp "Press Enter…" _ ;;
      3) cmd_config ;;
      4) cmd_create_all; read -rp "Press Enter…" _ ;;
      5)
        local sl; sl="$(ask "Tool slug" "")"
        [ -n "$sl" ] && cmd_create_one "$sl"
        read -rp "Press Enter…" _
        ;;
      6) cmd_install_local; read -rp "Press Enter…" _ ;;
      7) hop_menu ;;
      8) cmd_status; read -rp "Press Enter…" _ ;;
      9) cmd_smoke ;;
      10)
        local tag; tag="$(ask "Tag" "v0.1.0")"
        cmd_release_all "$tag"
        read -rp "Press Enter…" _
        ;;
      q|Q|"") clear 2>/dev/null; say "${C_GRN}bye 👋${C_RESET}"; exit 0 ;;
      *) warn "Unknown choice: $choice"; sleep 1 ;;
    esac
  done
}

# ----- entrypoint -----------------------------------------------------------
case "${1:-}" in
  wizard|setup-wizard|guided)
                shift; cmd_wizard "$@" ;;
  setup)        cmd_setup ;;
  auth)         cmd_auth ;;
  config)       cmd_config ;;
  create-all)   cmd_create_all ;;
  create)       shift; cmd_create_one "${1:-}" ;;
  status)       cmd_status ;;
  smoke)        cmd_smoke ;;
  install-all)  cmd_install_local ;;
  hop)          shift; [ -n "${1:-}" ] && project_menu "$1" || hop_menu ;;
  release-all)  shift; cmd_release_all "${1:-v0.1.0}" ;;
  list)         each_tool | awk '{printf "%-22s %-18s\n",$2,$1}' ;;
  -h|--help|help)
    cat <<EOH
Cognis Digital · Suite Launcher

  bash cognis-launcher.sh [command]

  wizard          Guided setup wizard — numbered menu, explains everything
                  (same as: ./setup.sh  or  .\\setup.ps1). Type a number.
  setup           Verify environment prerequisites (git / gh / python / pip)
  auth            GitHub CLI authentication
  config          Configure org / visibility / branch
  create-all      Create all repos + push files
  create <slug>   Create / re-push a single repo
  status          Status of all projects
  smoke           Multi-scenario smoke test
  install-all     Install all tools locally (pip -e)
  hop [slug]      Jump into a project (interactive if no slug)
  release-all [v] Tag & release all repos
  list            List tool slugs
  (no command)    Interactive main menu

Quick start (guided):  ./setup.sh    (or  .\\setup.ps1 )  — then type a number.
EOH
    ;;
  "" )          main_menu ;;
  *)            err "Unknown command: $1"; echo "see: bash cognis-launcher.sh --help" ;;
esac
