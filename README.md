# Roblox AI Skills

11 Roblox development skills and 7 optional specialist agents for code, maps, UI, 3D assets, textures, VFX, SFX, and animation. [SyphoDev](https://github.com/SyphoDev-yt/roblox-ai-skills) built the original Claude Code workflow; this fork adds an OpenAI Codex adapter.

**Codex status:** P0–P2 and maintenance passed independent **offline** audits. At [`d0e8b91`](https://github.com/haikalthrq/roblox-ai-skills/commit/d0e8b91f79a55a394b963a91865e3b58cf3a3742), Muse passed **38/38 tests** and [all 6 CI jobs](https://github.com/haikalthrq/roblox-ai-skills/actions/runs/40638249774) passed (Python 3.11/3.12 on Linux, macOS, Windows). **Live Codex skill discovery, Roblox Studio MCP, and subagent isolation are not yet validated.**

## Install

Requires a local checkout of this repository. Codex installation also requires Python 3.11+.

| | Claude Code | OpenAI Codex |
| --- | --- | --- |
| Installer | `install.ps1` (Windows) or `bash install.sh` (macOS/Linux) | `python codex/install.py` |
| Skill directory | `~/.claude/skills/` | `~/.agents/skills/` or `<project>/.agents/skills/` |
| Invoke | `/roblox-code` | `$roblox-code` |
| Setup | `/roblox-skills-setup` | `$roblox-skills-setup` |

**Codex: preview before installing.** Run from the repository root:

```bash
python codex/install.py --scope user
python codex/install.py --scope user --apply
```

For one workspace instead of your user account:

```bash
python codex/install.py --scope project --project-root "/path/to/workspace"
python codex/install.py --scope project --project-root "/path/to/workspace" --apply
```

Commands without `--apply` are dry runs. Existing destinations are not overwritten unless you explicitly use `--force --apply`; originals are backed up in `.codex-backups/` and existing `LOCAL.md` files are preserved. Interrupted installs have an explicit, **manual** recovery path. See [Codex install details](codex/README.md) and [troubleshooting](codex/TROUBLESHOOTING.md).

The installer does not install Roblox Studio, MCP servers, Rojo, Blender, other dependencies, or API credentials.

## Skills and tools

| Group | Skills |
| --- | --- |
| Workflow | `create-roblox-game`, `roblox-build-orchestrator`, `roblox-skills-setup` |
| Code and world | `roblox-code`, `roblox-map`, `roblox-ui` |
| Assets | `roblox-3d-model`, `roblox-texture-gen`, `roblox-vfx`, `roblox-sfx`, `roblox-animation` |

Different stages require different tools: Rojo, Wally, Lune, Selene and StyLua for code; Roblox Studio MCP for Studio tasks; Blender or external services for some assets. The original Kaggle GPU route is disabled. Check tool availability, cost, and asset licenses before use.

## Codex safety and validation

- Default installation runs stages **sequentially**, with **no custom subagents**. Seven optional TOML agents require explicit risk acceptance in a separately reviewed Studio-free session.
- Subagent prompts do **not** restrict MCP permissions. In a Studio-connected session, keep one primary Studio writer, one Studio MCP connection, one Rojo connection, and do not delegate to subagents.
- Offline tests verify the installer and generated copies; they do not verify a live game build, Studio access, crash atomicity, or runtime tool isolation. Use a disposable environment and separate approval for [runtime validation](codex/VALIDATION.md).
- A project's own decisions and approval gates override the generic workflow. Planning approval is not permission to build, test, or publish.

## Credits and license

Original skills: [SyphoDev](https://github.com/SyphoDev-yt/roblox-ai-skills). See [LICENSE.txt](LICENSE.txt): use and modify the skills for your own projects, including commercial games, but **do not sell the skills or modified packs**. Free redistribution requires attribution. Third-party tools, models, fonts, and assets have separate terms.
