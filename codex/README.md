# Codex adapter for Roblox AI Skills

This repository is a Claude Code-originated skill pack. The Codex adapter
creates working **copies** of all 11 skills. Conversion of the seven agent
definitions to Codex TOML is **off by default**: subagents may inherit the
parent session's Studio MCP access. The upstream `skills/`, `agents/`,
`install.sh`, and `install.ps1` remain unchanged.

## Start here

This installer is **dry-run first** and never installs external dependencies.
Choose **user scope** for personal skills, or **project scope** for one
existing workspace. Do not use a game repository or Project Antares as a
disposable test fixture. [Troubleshooting](TROUBLESHOOTING.md) covers refusals,
stale locks and failed recovery; [runtime validation](VALIDATION.md) is a
separate, explicitly authorized activity.

## Install into Codex

Requires Python 3.11+, Codex, and a checkout of this repository.

```bash
# In the repository root: inspect the targets, make no changes
python codex/install.py --scope user

# Only after you explicitly approve local installation
python codex/install.py --scope user --apply
```

Installed skill folders go to `~/.agents/skills/<name>/`. Agent definitions
are **not installed by default**; after an explicit opt-in, they go to
`~/.codex/agents/<name>.toml`.

To install only for a particular project instead of the whole user account:

```bash
python codex/install.py --scope project --project-root "/path/to/workspace"
python codex/install.py --scope project --project-root "/path/to/workspace" --apply
```

This installs skill copies into that project's `.agents/skills/`; optional
subagent definitions go to `.codex/agents/` only after explicit opt-in.
Project-scoped examples use project-root-relative paths; installed setup
scripts derive locations from their own file location, so relocating the
project does not embed the original machine's absolute paths. The installer
does not create or modify a Roblox game. Run generated relative-path examples
from the project root.

The installer refuses to replace an installed skill or agent by default.
Use `--force --apply` only after inspecting existing destinations and
authorizing their replacement. It creates a uniquely named backup in
`.codex-backups/` and preserves an existing `LOCAL.md`. Recoverable errors
trigger best-effort rollback; interruption recovery is manual. **It is not
crash-atomic.** Never store secrets in `LOCAL.md`.

## P1 installer concurrency and recovery

An applying installer creates a per-scope **`.codex-install.lock`** using atomic
exclusive creation. A second installer for that scope refuses to run. Dry-run
does not create a lock. The installer refuses symlinked destination paths,
source entries, and `LOCAL.md` links.

Before moving destinations, the installer stores a checksummed
`.codex-backups/<timestamp>-<id>/transaction.json` with `state: pending`.
Completed installs retain `state: complete` and prior backups. Ordinary
failures attempt rollback and record `state: recovered` when successful.
**Neither the journal nor rollback is a crash-atomic filesystem transaction.**

After an interruption, a **stale lock may remain**. Do not immediately
retry `--force`. Confirm no installer remains active, inspect the lock and
pending transaction, and preserve a separate copy of backups. Remove the stale
lock *manually* only after proving the process is stopped. Then explicitly
request recovery using the same scope and project root:

```bash
python codex/install.py --scope project --project-root "/path/to/workspace" --recover "/path/to/workspace/.codex-backups/<transaction-id>"
```

For user scope use `--scope user` and a transaction under `~/.codex-backups/`.
`--recover` **mutates files** and requires explicit authorization; it is
never automatic. Recovery verifies generated destinations **and original backups** against
recorded fingerprints before undoing moves. Unexpected user edits cause a
refusal without deleting them. If an original backup is missing, recovery
continues only when the unchanged original is still at its destination; it
never reports success when the original is missing. Inspect the transaction
and recovered tree before retrying the installer. See
[the diagnostic guide](TROUBLESHOOTING.md#recovery-after-an-interruption).

Locks are not auto-stolen by PID or age, because a PID may be reused and
removing a live lock can cause data loss. The supported recovery handles
tested process interruptions, not guaranteed power-loss durability,
filesystem corruption, external concurrent writes, or fully atomic rollback.
Keep independent backups of valuable files.


## How to invoke

Open Codex in the workspace containing the installed skills and ask it to
read and use `$roblox-skills-setup`, `$roblox-code`, `$roblox-map`,
or another installed skill. Do not assume Claude's `/skill-name` slash
commands are Codex commands.

The `create-roblox-game` skill can orchestrate a complete game workflow,
but it must not override an existing project plan or begin building because
a planning document was approved. Every build stage needs its own authorization.

## Runtime dependencies are separate

The installer **does not** install Roblox Studio, Rojo, Wally, Lune, Selene,
StyLua, Blender, Python libraries, GPU services, MCP servers, or API keys.
Follow `$roblox-skills-setup` only after verifying its suggested commands
and explicitly approving installations or checks. For the Studio MCP:
1. Configure Studio's official MCP server in Codex, using the supported
   Codex MCP interface and your local Studio version.
2. Confirm its tools can be discovered by Codex, before asking for Studio work.
3. Use exactly one Studio MCP connection and one Rojo connection. The
   primary Codex session owns all Studio writes and publication.
4. The upstream pack explicitly disables Kaggle GPU stages (2026-10-19);
   don't re-enable them as a Codex workaround. Check mesh-model licences.

## Subagents and orchestration

The default Codex installation is deliberately **sequential**. No custom
agent roles are installed, because custom agents can inherit the parent
session's MCP tools, including Roblox Studio tools.

Custom agents may inherit parent MCP tools. Only opt in for a separately verified Studio-free Codex session. The installer rejects enabled Studio/Roblox MCP in known configurations, but it cannot prove live tool isolation. This flag acknowledges inheritance risk:

```bash
python codex/install.py --scope user --enable-custom-agents --accept-subagent-mcp-inheritance
# After checking the dry run and approving installation:
python codex/install.py --scope user --enable-custom-agents --accept-subagent-mcp-inheritance --apply
```

`--accept-subagent-mcp-inheritance` is explicit **risk acceptance**, not proof of Studio MCP isolation. Built-in Codex agents may also inherit parent tools. Do not delegate Studio-connected work.

An existing Codex installation may contain custom TOML roles from any
source. Default `--apply` scans the user, `CODEX_HOME`, project-ancestor,
and invoking-directory ancestor agent locations, refusing to proceed if roles
exist. Dry-run displays those paths; built-in agents are unaffected. Review
the effective Codex multi-agent configuration before a Studio-connected
session. This installer cannot disable runtime workers for you.

When opted in, the installer converts the seven `agents/*.md` role descriptions
into standalone TOML under the Codex agent directory. The conversion carries over
the **role instructions**, not Claude's `tools`, `disallowedTools`, `model`,
`maxTurns`, or `skills` runtime semantics.

Codex runtime and surface support for custom subagents can vary. Confirm the
available spawn tool and whether the intended role is actually selected
before trusting a parallel build. In particular:

- Asset workers must not access Studio; their prompts do not enforce MCP permissions.
- The primary Codex session alone applies assets, tests in Studio, and publishes.
- A permission statement in a TOML prompt is **not** an MCP tool allow/deny list.
  Use Codex session permissions/tool exposure to enforce Studio isolation.
- In Studio-enabled sessions, perform stages sequentially
  and record that fallback. Do not report parallelism that did not occur.
- The `roblox-build-orchestrator` ledger, failure gates, and handoffs remain
  required regardless of whether execution is sequential or parallel.

## What has and has not been verified

P0–P2 and maintenance passed independent **offline** audits. At
[`d0e8b91`](https://github.com/haikalthrq/roblox-ai-skills/commit/d0e8b91f79a55a394b963a91865e3b58cf3a3742),
the Muse audit passed **38 tests**, and
[all six CI jobs](https://github.com/haikalthrq/roblox-ai-skills/actions/runs/40638249774)
succeeded. Earlier audited releases: P1
[`dc18907`](https://github.com/haikalthrq/roblox-ai-skills/commit/dc18907fd3d2591c24939bbe508dbba1ee667c5e)
(33 tests) and P2
[`45d6755`](https://github.com/haikalthrq/roblox-ai-skills/commit/45d675545666da06d74bc30b388927039803a3bb)
(37 tests). These are commit-specific offline results; live Codex and Studio
behaviour remains unverified. See the
[manual runtime evidence checklist](VALIDATION.md).

The adapter is a source-level conversion. Installed copies now adjust
`check_setup.py` environment discovery, `new_game.py` skill lookup, and
`preflight.py` fallback paths for Codex. Static review of this repository
is **not** proof of Codex role selection, Studio MCP access, tests passing,
or a functioning generated game. After an explicitly approved local install,
validate in this order: confirm Codex skill discovery; inspect required
tools and run only approved setup checks; if optional custom agents were
installed, verify their discovery and inherited access **in a Studio-free
session**; and only then separately authorize disposable-project code/map/UI
smoke tests and Studio MCP checks.

This repository is a **skill pack**, not the Project Antares game repository.
For Antares, carry forward its authoritative Wayfinder map, decisions
D-001 through D-256, any project glossary and permission gates. D-228 remains
UNPROVEN until a separately authorized runtime check supplies evidence. Do
not invent or silently migrate Antares decisions into this repository.
