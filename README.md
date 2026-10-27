# Roblox AI Skills — Claude Code + OpenAI Codex

Build Roblox games with an agent-assisted workflow for code, UI, maps, 3D models, textures, VFX, SFX, and animation. The pack contains **11 skills** and **7 specialist agent definitions**, plus scripts, checks, and handoff documents to organize work from design through playtesting.

This is a community fork of [SyphoDev's original `roblox-ai-skills`](https://github.com/SyphoDev-yt/roblox-ai-skills). **SyphoDev created the original Claude Code pipeline.** This fork retains it and adds a separate **OpenAI Codex adapter**. The adapter is a source-level port and **has not yet been validated end-to-end in a live Codex + Roblox Studio environment**.

## Choose your agent

| | Claude Code | OpenAI Codex |
| --- | --- | --- |
| Status | Original upstream workflow, preserved in this fork | Adapter implemented; runtime integration unverified |
| Installer | `install.ps1` (Windows) / `install.sh` (macOS/Linux) | `codex/install.py` (Windows/macOS/Linux with Python 3.11+) |
| Skill location | `~/.claude/skills/` | `~/.agents/skills/` (user) or `<project>/.agents/skills/` |
| Agent definitions | `~/.claude/agents/*.md` | Not installed by default; optional TOML under `~/.codex/agents/` or `<project>/.codex/agents/` |
| Invoke a skill | `/roblox-code` | `$roblox-code` |
| Detailed instructions | [Claude Code setup](#claude-code-setup) | [Codex setup](#openai-codex-setup) and [Codex adapter notes](codex/README.md) |

The Codex installer **copies and adjusts** the skills. Seven optional role definitions can be converted into TOML only through explicit MCP-inheritance risk acceptance in a Studio-free session. The adapter does not prove or enforce tool isolation. The default is sequential mode without custom subagents. This is not proof that every script, agent, or Studio interaction already works on the target machine. The Claude Code installer is **not** the Codex installer; do not run it to configure Codex.

## What is included

| Skill | Responsibility |
| --- | --- |
| `create-roblox-game` | Research, design contract, staged handoffs, assembly, playtest, and publish workflow |
| `roblox-build-orchestrator` | Coordinates stages, logs outcomes, and delegates independent file-only asset work when safe |
| `roblox-code` | Rojo + Knit project scaffold, Luau services, and four offline checks |
| `roblox-ui` | JSON-driven UI specs, preview images, Roblox UI artifacts, and verification |
| `roblox-map` | Level layout, blockout/terrain, reachability proofs, and map exports |
| `roblox-3d-model` | Mesh generation and Blender-to-Roblox asset preparation |
| `roblox-texture-gen` | Texture and material generation |
| `roblox-vfx` | Catalogs and reuses VFX from packs you are licensed to use; ships without a prebuilt VFX library |
| `roblox-sfx` | Finds, selects, and wires audio assets |
| `roblox-animation` | Headless Blender workflows for R6/R15 animations |
| `roblox-skills-setup` | Detects/configures local dependencies and per-skill `LOCAL.md` files |

Seven original role definitions live in [`agents/`](agents/): `roblox-asset-anim`, `roblox-asset-map`, `roblox-asset-mesh`, `roblox-asset-sfx`, `roblox-asset-ui`, `roblox-asset-vfx`, and `roblox-market-scout`. The Codex installer generates corresponding TOML files **only after explicit opt-in acknowledging inherited MCP risk, for Studio-free sessions**. Runtime agent discovery, delegation, and tool restrictions still need to be checked in the installed Codex environment.

### Workflow at a glance

```text
Research and design
       |
       v
Game contract + stage approvals
       |
       v
Code + map blockout -> offline build / test / lint / format
       |
       v
Map, meshes, textures, UI, animation, VFX, SFX
       |
       v
Single-writer integration in Roblox Studio
       |
       v
Playtest -> approved publication
```

The default `create-roblox-game` workflow uses **six sections**, each with a handoff and approval boundary. Asset tasks can be delegated only if the environment supports safe, isolated workers. Integration and Studio writes remain serial. An existing project's decisions, acceptance gates, and permissions take precedence over generic skill defaults.

## OpenAI Codex setup

Requirements for installing the adapter: **Python 3.11+**, an installed Codex environment, and a local copy of this repository. The commands below do **not** install Roblox Studio, MCP servers, Blender, or any other game-development dependency.

1. Clone or download this repository and open a terminal in its root folder.
2. Review the destinations **without changing any files**:

   ```bash
   python codex/install.py --scope user
   ```

3. When you approve installing the skills onto your machine, execute:

   ```bash
   python codex/install.py --scope user --apply
   ```

This installs adjusted skill copies under `~/.agents/skills/` but **does not install custom agents by default**. See [opt-in conditions](codex/README.md#subagents-and-orchestration). The source `skills/`, `agents/`, `install.ps1`, and `install.sh` remain unchanged.

To install only in one existing project:

```bash
python codex/install.py --scope project --project-root "/path/to/your/project"
# Inspect output first. Run the next command only when approved:
python codex/install.py --scope project --project-root "/path/to/your/project" --apply
```

Project scope writes skill copies into that project's `.agents/skills/`. Optional role TOML goes into `.codex/agents/` only after explicit risk acceptance in a Studio-free session; this is not verification of MCP isolation. The installer defaults to a **dry run**; `--apply` is required to change files. P1 adds an exclusive lock and a checksummed pending transaction journal for explicit recovery after process interruption. See [P1 recovery instructions](codex/README.md#p1-installer-concurrency-and-recovery). This is not crash-atomic. It scans existing custom agent TOML files across user and project scopes, blocking sequential-default installation when legacy roles remain. It refuses to replace existing installations unless you explicitly use `--force --apply`, which backs up old skill/agent paths under `.codex-backups/` and carries forward existing `LOCAL.md` files. Review local settings before replacing anything.

After installation, open Codex in the relevant workspace, confirm that the skills are discoverable, and invoke a skill by name, for example:

```text
$roblox-skills-setup
$roblox-code
$roblox-ui
```

**Do not immediately run an end-to-end build.** First inspect the setup skill's instructions and dependency checks. Only run setup commands, smoke tests, Studio actions, or game-generating scripts after giving those actions their own authorization.

See [`codex/README.md`](codex/README.md) for the detailed integration and verification steps, including Studio MCP and subagent limitations.

## Claude Code setup

The original workflow and installation scripts remain available:

1. Install [Claude Code](https://claude.com/claude-code) and Roblox Studio.
2. Clone or unzip this repository.
3. On Windows, run `install.ps1` using PowerShell. On macOS/Linux, run `bash install.sh`. Review the script before execution: it copies skill folders into `~/.claude/skills/` and agent definitions into `~/.claude/agents/` (with skill backups where applicable).
4. Restart Claude Code and invoke `/roblox-skills-setup`.

The setup skill detects local tools and writes per-skill `LOCAL.md` with your machine-specific paths. After setup and separate approval for build work, invoke a single skill or use `/create-roblox-game` to start the staged workflow.

## Dependencies by task

You do **not** need every tool for every skill. Neither installer installs these dependencies for you.

| Task | Tools / services to check |
| --- | --- |
| Agent + skill loading | Claude Code **or** Codex; Python 3.11+ for setup and the included scripts |
| Roblox Studio operations | Roblox Studio and its official Studio MCP, connected to the selected agent |
| Code scaffold and offline checks | Rojo, Wally, Lune, Selene, StyLua; the project uses Knit |
| UI, maps, VFX, SFX | Python scripts and their applicable Python dependencies; Studio for the steps that use the DataModel |
| Meshes and animation | Blender 4.x; supported mesh-generation service where required |
| Some 3D generation | Hugging Face access/token or the supported Kiln route, depending on the asset; verify availability, cost, and licensing |
| Permanent asset publication (optional) | Roblox Open Cloud API credentials and appropriate upload permissions |

The code workflow checks **Rojo build, Lune tests, Selene lint, and StyLua formatting** before Studio integration. These checks are only useful when run and reported; their presence in the repository is not evidence they passed on your machine.

For local configuration and optional stages, inspect [`roblox-skills-setup`](skills/roblox-skills-setup/SKILL.md). Store secrets in environment variables rather than chat messages or committed files. `LOCAL.md` is personal and should not be published.

## Codex subagents and Studio safety

The adapter can translate seven Markdown roles into Codex TOML, but it **installs no custom roles by default**. The optional inheritance-risk acknowledgment does not enforce Studio isolation. Until Studio MCP access is isolated and verified, asset stages must run sequentially. It **does not translate or enforce** Claude-specific `tools`, `disallowedTools`, `model`, `maxTurns`, or `skills` front matter.

- **Check runtime support.** Confirm Codex actually discovers the generated agent roles and has an available delegation mechanism. A TOML file on disk alone is not evidence a subagent ran.
- **Restrict tools at the execution layer.** A worker prompt saying "never use Studio" is **not** an enforced MCP permission boundary. Codex subagents may inherit the parent session's available tools and permissions; configure/review actual tool access before delegating.
- **Keep Studio single-writer.** Only the primary session should mutate Roblox Studio's shared DataModel, assemble assets, test in Studio, or publish. Maintain one Studio MCP connection and one Rojo connection.
- **Isolate file workers.** If safe agent/tool isolation is verified, parallelize independent asset work with distinct output paths and inspect the manifests before integration.
- **Use a sequential fallback.** If safe delegation cannot be verified, run those stages sequentially from the primary Codex session and report the fallback. Do not claim a parallel pipeline worked when it did not.

Project-specific plans and explicit approvals still govern implementation. A planning decision does not authorize installation, running tests, changing a game, accessing a paid service, or publishing assets.

## Known limitations and verification status

| Check | Current status for this fork |
| --- | --- |
| 11 source skills and 7 source agent definitions present | Present in repository |
| Codex installation adapter and optional TOML conversion code | Implemented on disk; not runtime-validated |
| Codex installation on an end user's computer | Not verified |
| Automatic Codex skill discovery and custom subagent execution | Not verified |
| Roblox Studio MCP connection / single-writer enforcement | Not verified |
| Four code checks and UI/map smoke tests against this Codex port | Not run as part of the adaptation |
| Blender / GPU asset generation from Codex | Not verified |
| Full Roblox game build, playtest, and publication | Not verified |

Tests for parts of the installer exist under [`tests/test_codex_installer.py`](tests/test_codex_installer.py), but adding tests is **not** the same as running them. Validate the target machine and toolchain before relying on this port for production development.

### Kaggle GPU pipeline is disabled

As of **2026-10-19**, upstream disabled the previous Kaggle GPU route. The original author reports account enforcement after using Kaggle for this pipeline. **Do not re-enable the Kaggle scripts as a Codex workaround.** The upstream workflow instead references Kiln for hard-surface assets and a Hugging Face Space for certain organic meshes; availability and terms must be checked before use. See [`roblox-3d-model/SKILL.md`](skills/roblox-3d-model/SKILL.md).

### VFX, model licences, and credentials

`roblox-vfx` ships without a VFX library. Harvest packs you have the right to use, then verify their licence terms before distribution. Models and third-party AI services carry their own restrictions; consult [the model licence notes](skills/roblox-3d-model/references/licences.md). Keep Roblox and Hugging Face tokens in local environment variables, not source files or a shared `LOCAL.md`.

## Repository layout

```text
skills/                Original Claude Code skill sources (11)
agents/                Original Claude Code agent definitions (7)
install.ps1            Original Windows installer for Claude Code
install.sh             Original macOS/Linux installer for Claude Code
codex/install.py       Dry-run-first Codex installer and adapter
codex/README.md        Extended Codex setup and verification notes
tests/                 Installer tests (execution not yet verified)
AGENTS.md              Repository instructions for Codex
LICENSE.txt            Original usage and redistribution terms
```

## Credits and licence

Original pack and workflow: **[SyphoDev](https://github.com/SyphoDev-yt/roblox-ai-skills)**, released free for the Roblox developer community. Original video walkthrough: [SyphoDev's Roblox AI workflow tutorial](https://www.youtube.com/watch?v=afuKhenJldY). This fork adds the Codex adapter and documentation; it does not claim authorship of the upstream skill designs.

Read [`LICENSE.txt`](LICENSE.txt) before redistributing the pack. The licence allows use and modification for your own projects, including commercial Roblox games, but **prohibits selling the skills or modified copies and putting them in paid bundles**. If you share the pack for free, credit the original creator and link back to the source/channel. Third-party tools, model weights, assets, and fonts have separate licence terms.
