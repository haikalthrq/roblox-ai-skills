# Working in this repository with Codex

This repository hosts reusable Roblox AI skills. It is not a Roblox game.
The original Claude Code skill pack under `skills/` and `agents/`
is source material. Codex adaptation lives in `codex/`; install working
copies through `codex/install.py`. Do not rewrite upstream assets merely
to make a Codex install work.

- Prefer small, reviewable changes; keep a clear distinction between
  documentation, source adaptation, actual installation, and runtime proof.
- Do not claim Codex, its custom subagents, Studio MCP, Blender, or GPU stages
  are working until checked in the target environment.
- No package/dependency installation, file generation in game repositories,
  test execution, Studio mutations, or publication without user authorization.
- Preserve the original requirement that only one main session writes to
  Roblox Studio. File-only asset workers must have disjoint output paths.
- Do not use Kaggle for this pack's disabled GPU pipeline. Do not expose keys.
- For Project Antares integrations, consult the actual game project's
  authoritative decisions and Wayfinder material before work. Do not assume
  those documents are present in this skill repository. Keep D-228 UNPROVEN
  absent valid test evidence; planning approval is not build approval.
