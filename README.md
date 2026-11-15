# RITMO / PulsoFlota

Spec-driven development workspace for **RITMO** (Riesgo, Incrementos y Trazabilidad para la
Movilidad Operativa) / **PulsoFlota**. The project is built with [GitHub Spec Kit](https://github.com/github/spec-kit)
driving the workflow and a set of custom [Kiro](https://kiro.dev) agents that run each Spec Kit
phase for you.

Project documentation lives in [`docs/`](docs/) (OMD, PRD, SRD — in Spanish).

---

## What's in this repo

| Path | What it is | Shared in git? |
|------|------------|----------------|
| `docs/` | Product/architecture/security docs (source of truth for the constitution) | ✅ |
| `.kiro/agents/` | The custom agents you run (one per workflow phase) | ✅ |
| `.kiro/prompts/speckit.*.md` | Spec Kit command prompts the agents follow | ✅ |
| `.specify/scripts/`, `.specify/templates/`, `.specify/memory/` | Spec Kit machinery (scripts, templates, constitution) | ✅ |
| `.specify/feature.json`, `.specify/integrations/packages/` | Machine-local Spec Kit state | ❌ (git-ignored) |
| `specs/` | Generated per-feature artifacts (spec, plan, tasks, checklists) | ✅ |

Because the agents and all Spec Kit files are committed, **you do not need to install Spec Kit
separately** — cloning the repo gives you everything the agents need.

---

## Prerequisites

Every contributor needs:

1. **Kiro** (IDE or CLI) — the agents are a Kiro feature. Install from [kiro.dev](https://kiro.dev).
2. **git**.
3. **Bash + `jq`** — the Spec Kit scripts are bash and use `jq` for JSON output.
4. **A language toolchain** once implementation starts (e.g. Node.js, Python) — matched to what the
   plan (`plan.md`) specifies for the feature.

### macOS / Linux

Bash is already present. Install `jq`:

```bash
# macOS (Homebrew)
brew install jq

# Debian / Ubuntu
sudo apt-get update && sudo apt-get install -y jq

# Fedora / RHEL
sudo dnf install -y jq
```

**No Homebrew on macOS?** Either install Homebrew first:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

…or install `jq` without it:

```bash
# MacPorts
sudo port install jq

# Or download the standalone binary and put it on your PATH
curl -L -o /usr/local/bin/jq https://github.com/jqlang/jq/releases/latest/download/jq-macos-arm64  # Apple Silicon
# For Intel Macs use jq-macos-amd64 instead
chmod +x /usr/local/bin/jq
```

Verify:

```bash
bash --version
jq --version
```

### Windows

The scripts are bash, so run them from a bash environment. Choose one:

- **WSL (recommended)** — install Ubuntu via `wsl --install`, then follow the Linux steps above
  (`sudo apt-get install -y jq`). Open the repo inside WSL.
- **Git Bash** — installed with [Git for Windows](https://git-scm.com/download/win). Then install
  `jq`:
  ```powershell
  winget install jqlang.jq
  ```
  (or download the `jq` binary and put it on your `PATH`).

Verify in your bash shell:

```bash
bash --version
jq --version
```

> Run Kiro and the agents from inside WSL/Git Bash so the `.specify/scripts/bash/*.sh` calls work.

---

## Getting started

```bash
git clone <repo-url>
cd RITMO
```

Open the folder in Kiro. The agents appear in the **agent picker** (bottom bar of the chat input).
Nothing else to install — the committed `.kiro/` and `.specify/` directories are the whole setup.

---

## Optional: installing the Spec Kit CLI

You **do not need this** to run the agents in this repo — the Spec Kit files are already committed.
Install the CLI only if you want to scaffold Spec Kit into another project, upgrade/re-generate the
`.specify/` machinery, or run the `/speckit-*` commands directly outside these agents.

Official guide: <https://github.github.io/spec-kit/installation.html>

**Prerequisites for the CLI:** Python 3.11+, and `uv` (recommended) or `pipx`/`pip`. Git is optional
(needed only if the git extension is enabled).

### Install (all users)

Spec Kit is published as `specify-cli`. Pick one:

```bash
# Using uv (recommended)
uv tool install specify-cli

# Or using pipx
pipx install specify-cli

# Or using pip
pip install specify-cli

# Or pin to a specific release from source (keep the leading v)
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z
```

Getting `uv`:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# (or: brew install uv)

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:

```bash
specify version
```

### Scaffold a project

```bash
# New project
specify init <project_name> --integration copilot

# Into an existing (non-empty) directory — review/commit first
specify init --here --force --integration copilot
```

Swap `copilot` for your agent integration (`claude`, `gemini`, `codebuddy`, `pi`, `omp`, or `none`
for agent-neutral scaffolding).

**Script variant — important for Windows.** Spec Kit can emit Bash, PowerShell, or Python helper
scripts. The agents in this repo call the **Bash** scripts under `.specify/scripts/bash/`, so if you
re-scaffold, keep the bash variant:

```bash
specify init <project_name> --script sh    # Bash  (what these agents use)
specify init <project_name> --script ps    # PowerShell (native Windows, no WSL needed)
specify init <project_name> --script py    # Python
```

> Windows can now use PowerShell scripts natively (`--script ps`, no WSL required). But this repo's
> agents are wired to the `bash` scripts, so to run *these* agents on Windows you still need WSL or
> Git Bash as described in Prerequisites. If you prefer native PowerShell, you'd need to re-point the
> agents at `.specify/scripts/powershell/` — not required for the committed setup.

For enterprise/air-gapped installs, upgrades, and one-time `uvx` usage, see the official guide above.

---

## The agents (workflow pipeline)

Each agent wraps one Spec Kit command. Select an agent in the picker, then send your request.
After most agents finish, a **handoff button** offers the next step, so you can walk the chain with
one click per phase.

```
create-context            (standalone — run first / when docs change)
      │
create-spec ─▶ create-plan ─▶ create-tasks ─▶ validate-plan ─▶ implement-code ─▶ review-code
                                                                                       │
                                                                                       └─▶ implement-code   (loop back while work remains)
```

| Agent | Spec Kit prompt | What it does |
|-------|-----------------|--------------|
| **create-context** | `speckit.constitution` | Reads `docs/` and creates/updates `constitution.md`, `AGENTS.md`, and `.kiro/steering/` files. Standalone (no handoff). |
| **create-spec** | `speckit.specify` | Creates a feature spec under `specs/<id>-<name>/spec.md`. |
| **create-plan** | `speckit.plan` | Creates the technical plan + design artifacts for the current feature. |
| **create-tasks** | `speckit.tasks` | Generates `tasks.md`. Test tasks are **ON by default** unless the spec/constitution opts out. |
| **validate-plan** | `speckit.analyze` + `speckit.checklist` | Pre-implementation gate: cross-artifact consistency, then requirements-quality checklist. Stops on CRITICAL findings or missing `tasks.md`. |
| **implement-code** | `speckit.implement` | Executes `tasks.md` to write the code; marks tasks `[X]`. The only agent that edits source and runs build/test commands. |
| **review-code** | `speckit.converge` + `speckit.implement` | Finds unbuilt/incorrect work vs the spec, re-runs implement for it, then runs full tests + coverage, lint, format, and other validations; fixes what's safe or writes `specs/<feature>/review-findings.md`. Loops back to implement-code while gaps remain. |

### Typical first run on a fresh clone

1. **create-context** — build the constitution, `AGENTS.md`, and steering from `docs/`.
2. **create-spec** — describe the feature you want.
3. Follow the handoff buttons: **create-plan → create-tasks → validate-plan → implement-code → review-code**.
4. If **review-code** reports appended work (`tasks_appended`), click **Re-run Implement** and let
   review-code run again. Repeat until it reports `converged`.

---

## Notes

- **Per-feature state:** `.specify/feature.json` points at the current feature directory and is
  git-ignored (it's per-checkout). Each contributor's agents resolve the feature locally.
- **Committing:** the agents never commit for you (`git commit`/`push` are blocked in agent
  permissions). Review changes and commit yourself.
- **Coverage threshold:** `review-code` reads the minimum from the constitution/test config; if none
  is set it asks, defaulting to 80% only as a last resort. Define it in the constitution to make it
  consistent for everyone.
